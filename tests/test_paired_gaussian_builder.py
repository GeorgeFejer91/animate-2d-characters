"""Adversarial correspondence tests for alpha-zero endpoint support."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np


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


if __name__ == "__main__":
    unittest.main()
