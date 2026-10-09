"""Adversarial correspondence tests for alpha-zero endpoint support."""
import importlib.util
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_paired_gaussian", ROOT / "scripts/build_paired_gaussian.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def painting(points):
    xy = np.asarray(points, dtype=float).reshape(-1, 2)
    rgba = np.tile(np.array([[171, 61, 43, 255]], dtype="u1"), (len(xy), 1))
    return xy, rgba


def state(prop_x, guide):
    return {"id": str(prop_x), "landmarks": {"guide": [guide, 0]},
            "regions": [{"part": "prop", "polygon": [[prop_x - 2, 3], [prop_x + 3, 3],
                                                    [prop_x + 3, 7], [prop_x - 2, 7]]}]}


class SyntheticEndpointTests(unittest.TestCase):
    def check_visible(self, block, source, target):
        start, end, color_start, color_end, _ = block
        for coordinates, paint, original in ((start, color_start, source), (end, color_end, target)):
            expected = {(tuple(xy), tuple(rgba)) for xy, rgba in zip(*original)}
            actual = {(tuple(xy), tuple(rgba)) for xy, rgba in zip(coordinates, paint) if rgba[3]}
            self.assertEqual(actual, expected, "every visible key sample stays exact")

    def test_birth_stays_on_its_own_support_despite_displaced_landmarks(self):
        source, target = painting([[5, 5], [30, 5]]), painting([[20, 5], [21, 5], [30, 5]])
        block = BUILDER.match(source, target, state(5, 0), state(20, 50), 2, 64, 16)
        self.check_visible(block, source, target)
        start, _, color_start, color_end, ranges = block
        born = [n for n in range(*ranges["prop"]) if not color_start[n, 3] and color_end[n, 3]]
        self.assertEqual(len(born), 1)
        self.assertLessEqual(np.linalg.norm(start[born[0]] - [5, 5]), 2)
        self.assertGreater(np.linalg.norm(start[born[0]] - [30, 5]), 2,
                           "body pixels are not valid support for a born prop")

    def test_death_stays_on_its_own_support_despite_displaced_landmarks(self):
        source, target = painting([[5, 5], [6, 5], [55, 5]]), painting([[20, 5], [55, 5]])
        block = BUILDER.match(source, target, state(5, 0), state(20, 50), 2, 64, 16)
        self.check_visible(block, source, target)
        _, end, color_start, color_end, ranges = block
        dying = [n for n in range(*ranges["prop"]) if color_start[n, 3] and not color_end[n, 3]]
        self.assertEqual(len(dying), 1)
        self.assertLessEqual(np.linalg.norm(end[dying[0]] - [20, 5]), 2)
        self.assertGreater(np.linalg.norm(end[dying[0]] - [55, 5]), 2,
                           "body pixels are not valid support for a dying prop")

    def test_absent_part_uses_stationary_visible_endpoint(self):
        cases = [
            (painting([[30, 5]]), painting([[20, 5], [30, 5]]), True),
            (painting([[5, 5], [30, 5]]), painting([[30, 5]]), False),
        ]
        for source, target, birth in cases:
            with self.subTest(birth=birth):
                block = BUILDER.match(source, target, state(5, 0), state(20, 50), 2, 64, 16)
                self.check_visible(block, source, target)
                start, end, color_start, color_end, ranges = block
                slots = range(*ranges["prop"])
                if birth:
                    slot = next(n for n in slots if not color_start[n, 3])
                    np.testing.assert_array_equal(start[slot], end[slot])
                else:
                    slot = next(n for n in slots if not color_end[n, 3])
                    np.testing.assert_array_equal(end[slot], start[slot])

    def test_nearby_extrapolation_within_one_stride_is_retained(self):
        source, target = painting([[5, 5]]), painting([[5, 5], [6, 5]])
        block = BUILDER.match(source, target, state(5, 0), state(5, 0), 2, 64, 16)
        self.check_visible(block, source, target)
        start, end, color_start, _, ranges = block
        slot = next(n for n in range(*ranges["prop"]) if not color_start[n, 3])
        np.testing.assert_array_equal(start[slot], end[slot])
        self.assertEqual(tuple(start[slot]), (6.0, 5.0))

    def test_runtime_anchor_webp_is_lossless_with_zero_hidden_rgb(self):
        built = ROOT / "assets/paired-gaussian/fixture/built"
        manifest = json.loads((built / "synthetic-action.json").read_text())
        self.assertEqual(manifest["anchors"]["maximum_resident"], 3)
        self.assertEqual(manifest["anchors"]["fade_seconds"], .09)
        for state in manifest["states"]:
            frame = manifest["anchors"]["frames"][state["id"]]
            encoded = (built / frame["file"]).read_bytes()
            self.assertEqual(len(encoded), frame["bytes"])
            self.assertEqual(hashlib.sha256(encoded).hexdigest(), frame["sha256"])
            rgba = np.asarray(Image.open(built / frame["file"]).convert("RGBA"))
            self.assertEqual(list(rgba.shape), [*manifest["canvas_xy"][::-1], 4])
            self.assertTrue(np.all(rgba[rgba[:, :, 3] == 0, :3] == 0))
            self.assertEqual(hashlib.sha256(rgba.tobytes()).hexdigest(), frame["rgba_sha256"])

    def test_optional_paint_warp_gains_survive_manifest_build(self):
        fixture = ROOT / "assets/paired-gaussian/fixture"
        spec = json.loads((fixture / "spec.json").read_text())
        for entry in spec["states"]:
            entry["file"] = str(fixture / entry["file"])
        spec["paint_warp_gains"] = [0, .4, 1]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "spec.json"
            path.write_text(json.dumps(spec))
            manifest = BUILDER.build(path, Path(directory) / "out")
            self.assertEqual([pair["paint_warp_gain"] for pair in manifest["segments"]], [0, .4, 1])
            self.assertEqual([(pair["from"], pair["to"]) for pair in manifest["segments"]],
                             [("work", "bridge"), ("bridge", "gesture"), ("work", "gesture")])
            del spec["paint_warp_gains"]
            path.write_text(json.dumps(spec))
            without = BUILDER.build(path, Path(directory) / "out-no-gain")
            self.assertTrue(all("paint_warp_gain" not in pair for pair in without["segments"]))

    def test_paint_warp_gain_array_rejects_bad_count_or_value(self):
        fixture = ROOT / "assets/paired-gaussian/fixture"
        spec = json.loads((fixture / "spec.json").read_text())
        for entry in spec["states"]:
            entry["file"] = str(fixture / entry["file"])
        bad = [[0], None, "0.1", [0, float("nan"), 1], [0, float("inf"), 1],
               [-.01, .4, 1], [0, .4, 1.01], [0, True, 1], [0, "0.4", 1]]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "spec.json"
            for values in bad:
                with self.subTest(values=values):
                    spec["paint_warp_gains"] = values
                    path.write_text(json.dumps(spec))
                    with self.assertRaisesRegex(ValueError, "paint_warp_gains"):
                        BUILDER.build(path, Path(directory) / "out")


if __name__ == "__main__":
    unittest.main()
