"""Build deterministic paired-paint Gaussian arcs from registered RGBA keys.

Requires NumPy, Pillow and SciPy, already used by this skill's image tools. It proposes
correspondences within explicitly named regions; visual anatomy still needs review.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

WIDTH = 256
MAX_TRAJECTORIES_PER_SEGMENT = 8
MAX_TRAJECTORIES = 64
RECORD = np.dtype([("xy", "<f4", (4,)), ("start", "u1", (4,)), ("end", "u1", (4,))])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inside_polygon(points, polygon):
    poly = np.asarray(polygon, dtype=float)
    if poly.ndim != 2 or poly.shape[1] != 2 or len(poly) < 3:
        raise ValueError("Region polygon needs at least three XY vertices")
    x, y = points.T
    hit = np.zeros(len(points), dtype=bool)
    for a, b in zip(poly, np.roll(poly, 1, axis=0)):
        crossing = ((a[1] > y) != (b[1] > y)) & (x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1] + 1e-12) + a[0])
        hit ^= crossing
    return hit


def ownership(points, state):
    names = np.full(len(points), "body", dtype=object)
    for region in state.get("regions", []):
        if not isinstance(region.get("part"), str) or not region["part"]:
            raise ValueError("Each region needs a named part")
        names[inside_polygon(points, region["polygon"])] = region["part"]
    return names


def curved_region(state, part):
    regions = [region for region in state.get("regions", []) if region["part"] == part]
    marked = [region for region in regions if "pivot_xy" in region or "orientation_landmarks" in region]
    if not marked:
        return None
    if len(marked) != 1 or len(regions) != 1:
        raise ValueError(f"Curved part {part!r} needs one owned region per state")
    return marked[0]


def curve_between(source, target, part, width, height):
    first, last = curved_region(source, part), curved_region(target, part)
    if first is None and last is None:
        return None
    if first is None or last is None:
        raise ValueError(f"Curved part {part!r} needs a pivot and orientation in both keys")
    names = first.get("orientation_landmarks")
    if not isinstance(names, list) or len(names) != 2 or names == names[::-1] or not all(isinstance(n, str) and n for n in names) or last.get("orientation_landmarks") != names:
        raise ValueError(f"Curved part {part!r} needs the same two named orientation landmarks in both keys")
    def point(value, label):
        arr = np.asarray(value, dtype=float)
        if arr.shape != (2,) or not np.isfinite(arr).all() or not (0 <= arr[0] <= width and 0 <= arr[1] <= height):
            raise ValueError(f"Invalid {label} for curved part {part!r}")
        return arr
    pivots = [point(region.get("pivot_xy"), "pivot_xy") for region in (first, last)]
    directions = []
    for state in (source, target):
        landmarks = state["landmarks"]
        if any(name not in landmarks for name in names):
            raise ValueError(f"Missing orientation landmark for curved part {part!r}")
        a, b = [point(landmarks[name], name) for name in names]
        vector = b - a
        vector[1] *= -1  # normalized Gaussian coordinates point upward
        if np.linalg.norm(vector) < 1:
            raise ValueError(f"Degenerate orientation for curved part {part!r}")
        directions.append(vector)
    a, b = directions
    angle = math.atan2(float(a[0] * b[1] - a[1] * b[0]), float(a @ b))
    def normalized(pivot):
        result = [float((pivot[0] - width / 2) / height), float((height - pivot[1]) / height)]
        if any(abs(value) > 4 for value in result):
            raise ValueError(f"Curved part {part!r} pivot exceeds the bounded Gaussian canvas")
        return result
    return {"pivot_start": normalized(pivots[0]), "pivot_end": normalized(pivots[1]), "angle_radians": angle}


def check_curved_ownership(state, points):
    occupied = np.zeros(len(points), dtype=bool)
    for region in state.get("regions", []):
        if "pivot_xy" not in region and "orientation_landmarks" not in region:
            continue
        covered = inside_polygon(points, region["polygon"])
        if np.any(occupied & covered):
            raise ValueError(f"Overlapping curved regions in {state['id']}")
        occupied |= covered


def transport(points, source, target, radius):
    common = sorted(set(source["landmarks"]) & set(target["landmarks"]))
    if not common:
        raise ValueError("Adjacent keys need shared named landmarks")
    src = np.asarray([source["landmarks"][name] for name in common], dtype=float)
    dst = np.asarray([target["landmarks"][name] for name in common], dtype=float)
    if src.shape[1:] != (2,) or not np.isfinite(src).all() or not np.isfinite(dst).all():
        raise ValueError("Landmarks must be finite XY pairs")
    weights = 1 / (((points[:, None] - src[None]) ** 2).sum(axis=2) + radius**2)
    weights /= weights.sum(axis=1, keepdims=True)
    return points + weights @ (dst - src)


def samples(image, stride):
    w, h = image.size
    yy, xx = np.mgrid[max(0, stride // 2):h:stride, max(0, stride // 2):w:stride]
    rgba = np.asarray(image)[yy, xx].reshape(-1, 4)
    xy = np.column_stack((xx.ravel(), yy.ravel())).astype(float)
    keep = rgba[:, 3] > 6
    return xy[keep], rgba[keep]


def match(source_sample, target_sample, source, target, stride, width, height):
    ax, ac = source_sample
    bx, bc = target_sample
    ap, bp = ownership(ax, source), ownership(bx, target)
    predict = transport(ax, source, target, stride * 4)
    back = transport(bx, target, source, stride * 4)
    pairs, ranges = [], {}
    for part in sorted(set(ap) | set(bp)):
        first_slot = len(pairs)
        ai = np.flatnonzero(ap == part)
        bi = np.flatnonzero(bp == part)
        curve = curve_between(source, target, part, width, height)
        if curve:
            # Match a rotating owned part in its authored local frame. A straight
            # spatial cost pairs opposite sides of a half-turned prop.
            pa, pb = [np.array([pivot[0] * height + width / 2, height - pivot[1] * height])
                      for pivot in (curve["pivot_start"], curve["pivot_end"])]
            def rotated(points, radians):
                cosine, sine = math.cos(radians), math.sin(radians)
                x, y = points.T
                return np.column_stack((cosine * x - sine * y, sine * x + cosine * y))
            # Image Y points down, opposite to the shader's normalized Y.
            predict[ai] = pb + rotated(ax[ai] - pa, -curve["angle_radians"])
            back[bi] = pa + rotated(bx[bi] - pb, curve["angle_radians"])
        if not len(ai):
            pairs.extend((None, int(j)) for j in bi)
        elif not len(bi):
            pairs.extend((int(i), None) for i in ai)
        else:
            # Dense global assignment fixes row-order depletion of greedy matching.
            # Split large artwork into named parts before a quadratic matrix grows.
            if len(ai) * len(bi) > 4_000_000:
                raise ValueError(f"Part {part!r} needs finer ownership regions or a coarser sampling stride")
            cost = cdist(predict[ai], bx[bi], "sqeuclidean") * .5
            cost += cdist(ax[ai], back[bi], "sqeuclidean") * .5
            cost += cdist(ac[ai, :3].astype(float), bc[bi, :3].astype(float), "sqeuclidean") * .001
            rows, cols = linear_sum_assignment(cost)
            used_a, used_b = set(), set()
            for row, col in zip(rows, cols):
                i, j = int(ai[row]), int(bi[col])
                pairs.append((i, j))
                used_a.add(i)
                used_b.add(j)
            pairs.extend((int(i), None) for i in ai if int(i) not in used_a)
            pairs.extend((None, int(j)) for j in bi if int(j) not in used_b)
        ranges[part] = (first_slot, len(pairs))
    a = np.zeros((len(pairs), 2), dtype=float)
    b = np.zeros_like(a)
    c0 = np.zeros((len(pairs), 4), dtype="u1")
    c1 = np.zeros_like(c0)
    for n, (i, j) in enumerate(pairs):
        a[n] = ax[i] if i is not None else back[j]
        b[n] = bx[j] if j is not None else predict[i]
        if i is not None:
            c0[n] = ac[i]
        if j is not None:
            c1[n] = bc[j]
    return a, b, c0, c1, ranges


def build(spec_path, output):
    spec_path = Path(spec_path).resolve()
    output = Path(output).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    ident, (w, h) = spec["id"], spec["canvas_xy"]
    if not ident.replace("-", "").replace("_", "").isalnum() or not (0 < w <= 4096 and 0 < h <= 4096):
        raise ValueError("Invalid id or canvas")
    states = spec["states"]
    by_id = {state["id"]: state for state in states}
    if len(by_id) != len(states) or len(states) < 2:
        raise ValueError("States need unique IDs")
    images = {}
    for state in states:
        source = (spec_path.parent / state["file"]).resolve()
        image = Image.open(source).convert("RGBA")
        if "crop_xywh" in state:
            x, y, cw, ch = state["crop_xywh"]
            image = image.crop((x, y, x + cw, y + ch))
        if image.size != (w, h):
            raise ValueError(f"{state['id']} has canvas {image.size}, expected {(w, h)}")
        images[state["id"]] = image
        state["sha256"] = digest(source.read_bytes())
    segments, lookup = [], {}
    for arc in spec["arcs"]:
        keys = arc.pop("keys")
        if len(keys) < 2 or keys[0]["time"] != 0 or any(keys[i + 1]["time"] <= keys[i]["time"] for i in range(len(keys) - 1)):
            raise ValueError("Arc keys need increasing time from zero")
        arc.update({"from": keys[0]["state"], "to": keys[-1]["state"], "duration": keys[-1]["time"], "segments": []})
        for a, b in zip(keys, keys[1:]):
            pair = (a["state"], b["state"])
            if pair[0] not in by_id or pair[1] not in by_id:
                raise ValueError("Arc references an unknown state")
            if pair not in lookup:
                lookup[pair] = len(segments)
                segments.append(pair)
            arc["segments"].append({"segment": lookup[pair], "start": a["time"], "end": b["time"]})
    if not 1 <= len(segments) <= 32:
        raise ValueError("Expected 1..32 segments")
    output.mkdir(parents=True, exist_ok=True)
    variants = {}
    for variant, stride in spec["variants"].items():
        if not isinstance(stride, int) or not 1 <= stride <= 32:
            raise ValueError("Variant stride must be 1..32 pixels")
        sampled = {state["id"]: samples(images[state["id"]], stride) for state in states}
        for state in states:
            check_curved_ownership(state, sampled[state["id"]][0])
        blocks = [match(sampled[a], sampled[b], by_id[a], by_id[b], stride, w, h) for a, b in segments]
        count = ((max(len(block[0]) for block in blocks) + WIDTH - 1) // WIDTH) * WIDTH
        if not 1 <= count <= 20000:
            raise ValueError("Too many matched samples")
        records = np.zeros((len(segments), count), dtype=RECORD)
        trajectories = []
        for segment, (a, b, start, end, ranges) in enumerate(blocks):
            source_state, target_state = (by_id[key] for key in segments[segment])
            curved_parts = sorted({region["part"] for state in (source_state, target_state)
                                   for region in state.get("regions", [])
                                   if "pivot_xy" in region or "orientation_landmarks" in region})
            for part in curved_parts:
                curve = curve_between(source_state, target_state, part, w, h)
                first_slot, end_slot = ranges.get(part, (0, 0))
                if first_slot == end_slot:
                    raise ValueError(f"Curved part {part!r} has no sampled paint")
                trajectories.append({"segment": segment, "start_slot": first_slot, "end_slot": end_slot, **curve})
            if sum(item["segment"] == segment for item in trajectories) > MAX_TRAJECTORIES_PER_SEGMENT or len(trajectories) > MAX_TRAJECTORIES:
                raise ValueError("Too many curved regions for one variant")
            a = np.column_stack(((a[:, 0] - w / 2) / h, (h - a[:, 1]) / h))
            b = np.column_stack(((b[:, 0] - w / 2) / h, (h - b[:, 1]) / h))
            n = len(a)
            records[segment, :n]["xy"] = np.column_stack((a, b))
            records[segment, :n]["start"] = start
            records[segment, :n]["end"] = end
        raw = records.tobytes()
        compressed = gzip.compress(raw, mtime=0)
        file = f"{ident}-{variant}.bin.gz"
        (output / file).write_bytes(compressed)
        variants[variant] = {"file": file, "sha256": digest(compressed), "decoded_sha256": digest(raw), "bytes": len(compressed), "decoded_bytes": len(raw), "sample_count": count, "stride_px": stride, "segment_count": len(segments), "record_bytes": 24}
        if trajectories:
            variants[variant]["trajectories"] = trajectories
    manifest = {"version": 1, "id": ident, "representation": "paired-gaussian-paint", "canvas_xy": [w, h],
                "states": states, "arcs": spec["arcs"], "segments": [{"from": a, "to": b} for a, b in segments], "variants": variants,
                "speech_landmarks": spec.get("speech_landmarks", []), "speech_radius_px": spec.get("speech_radius_px", [12, 8]), "speech_amplitude_px": spec.get("speech_amplitude_px", 1)}
    (output / f"{ident}.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.spec, args.output)
    print(json.dumps({"id": result["id"], "variants": result["variants"]}))
