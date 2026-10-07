"""Fit ground distance per walk cycle from marked stance-foot positions.

Input positions are measured in the *exported* atlas cell, along the character's
travel direction. A contact is one named foot while its sole is planted.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import tempfile


def assess(data):
    frames = int(data["frames_per_cycle"])
    scale = float(data["game_units_per_pixel"])
    current = float(data["current_cycle_distance"])
    shoe = float(data["shoe_length_pixels"])
    if frames < 2 or min(scale, current, shoe) <= 0:
        raise ValueError("Frame count must be at least 2; scale, distance and shoe length must be positive")

    groups = []
    for contact in data["contacts"]:
        samples = [(float(p["frame"]) / frames, float(p["along_pixels"]) * scale)
                   for p in contact["samples"]]
        if len(samples) < 2 or len({phase for phase, _ in samples}) < 2:
            raise ValueError("Each planted-foot contact needs at least two different frame positions")
        if any(not math.isfinite(value) for pair in samples for value in pair):
            raise ValueError("Contact measurements must be finite")
        groups.append((contact["foot"], samples))
    if not groups:
        raise ValueError("At least one planted-foot contact is required")

    # A fixed point on the ground has world position root + foot. Each contact
    # gets its own unknown world intercept, so only its within-contact slope
    # determines the cycle distance.
    covariance = variance = 0.0
    for _, samples in groups:
        mean_phase = sum(phase for phase, _ in samples) / len(samples)
        mean_foot = sum(foot for _, foot in samples) / len(samples)
        covariance += sum((phase - mean_phase) * (foot - mean_foot)
                          for phase, foot in samples)
        variance += sum((phase - mean_phase) ** 2 for phase, _ in samples)
    fitted = -covariance / variance
    if fitted <= 0:
        raise ValueError("Marked stance foot does not travel backward; check foot identity, direction and contacts")

    def slip(distance):
        errors = []
        for _, samples in groups:
            points = [distance * phase + foot for phase, foot in samples]
            centre = sum(points) / len(points)
            errors.extend(point - centre for point in points)
        return {"rms_game_units": math.sqrt(sum(e * e for e in errors) / len(errors)),
                "max_game_units": max(abs(e) for e in errors)}

    contact_distances = []
    for foot, samples in groups:
        mean_phase = sum(phase for phase, _ in samples) / len(samples)
        mean_foot = sum(offset for _, offset in samples) / len(samples)
        spread = sum((phase - mean_phase) ** 2 for phase, _ in samples)
        distance = -sum((phase - mean_phase) * (offset - mean_foot)
                        for phase, offset in samples) / spread
        contact_distances.append({"foot": foot, "fitted_cycle_distance": distance})
    current_slip, fitted_slip = slip(current), slip(fitted)
    previous = data.get("previous_cycle_distance")
    previous_slip = slip(float(previous)) if previous is not None else None
    shoe_units = shoe * scale
    for result in (current_slip, fitted_slip, previous_slip):
        if result is None:
            continue
        result["rms_shoe_lengths"] = result["rms_game_units"] / shoe_units
        result["max_shoe_lengths"] = result["max_game_units"] / shoe_units
    return {"character": data.get("character"), "view": data.get("view"),
            "atlas_sha256": data.get("atlas_sha256"), "contacts": len(groups),
            "sample_count": sum(len(samples) for _, samples in groups),
            "both_feet_observed": len({foot for foot, _ in groups}) >= 2,
            "per_contact_distances": contact_distances,
            "current_cycle_distance": current, "fitted_cycle_distance": fitted,
            "distance_ratio_fitted_to_current": fitted / current,
            "current_slip": current_slip, "fitted_slip": fitted_slip,
            **({"previous_cycle_distance": previous, "previous_slip": previous_slip}
               if previous_slip is not None else {})}


def self_test():
    source = {"frames_per_cycle": 8, "game_units_per_pixel": 0.5,
              "current_cycle_distance": 40, "shoe_length_pixels": 20,
              "contacts": [{"foot": name, "samples": [
                  {"frame": frame, "along_pixels": offset - 48 * frame / 8}
                  for frame in range(start, start + 3)]}
                  for name, start, offset in (("left", 1, 20), ("right", 5, 50))]}
    result = assess(source)
    assert math.isclose(result["fitted_cycle_distance"], 24, abs_tol=1e-10)
    assert result["fitted_slip"]["rms_game_units"] < 1e-10
    assert result["current_slip"]["rms_game_units"] > 0
    source["contacts"][0]["samples"] = [{"frame": 1, "along_pixels": 0}]
    try:
        assess(source)
    except ValueError:
        pass
    else:
        raise AssertionError("Single-frame contact was accepted")
    with tempfile.TemporaryDirectory() as directory:
        atlas = Path(directory) / "atlas.png"
        atlas.write_bytes(b"accepted pixels")
        source["contacts"][0]["samples"] = [
            {"frame": frame, "along_pixels": 20 - 48 * frame / 8}
            for frame in range(1, 4)]
        source["atlas_file"] = "atlas.png"
        source["atlas_sha256"] = hashlib.sha256(atlas.read_bytes()).hexdigest()
        record = Path(directory) / "measurements.json"
        record.write_text(json.dumps(source), encoding="utf-8")
        assert math.isclose(assess_file(record)["fitted_cycle_distance"], 24)
        atlas.write_bytes(b"changed pixels")
        try:
            assess_file(record)
        except ValueError:
            pass
        else:
            raise AssertionError("Changed atlas was accepted with stale measurements")


def assess_file(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("assessments", [data])
    results = []
    for entry in entries:
        if "atlas_file" not in entry or "atlas_sha256" not in entry:
            raise ValueError("atlas_file and atlas_sha256 are required for every assessment")
        atlas = (path.parent / entry["atlas_file"]).resolve()
        actual = hashlib.sha256(atlas.read_bytes()).hexdigest()
        if actual != entry["atlas_sha256"]:
            raise ValueError("atlas SHA-256 does not match measurement record: " + str(atlas))
        results.append(assess(entry))
    if len(results) == 1:
        return results[0]
    by_character = {}
    for result in results:
        by_character.setdefault(result["character"], []).append(result)
    return {"assessments": results,
            "character_means": {name: sum(r["fitted_cycle_distance"] for r in views) / len(views)
                                for name, views in by_character.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurements", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("walk-speed assessment self-test passed")
    elif args.measurements:
        print(json.dumps(assess_file(args.measurements), indent=2))
    else:
        parser.error("provide a measurement JSON or --self-test")
