"""Regenerate the deliberately simple, unapproved synthetic correspondence fixture."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

def make(output):
    output.mkdir(parents=True, exist_ok=True)
    for name, tip in [("work", (51, 34)), ("bridge", (50, 20)), ("gesture", (44, 9))]:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((23, 24, 41, 54), fill=(37, 72, 117, 255))
        draw.ellipse((25, 8, 39, 23), fill=(227, 191, 146, 255))
        # The red line is the named held_baton in spec.json, rotating about
        # the fixed grip (39, 29). The direct swing arc uses the outer keys.
        draw.line(((39, 29), tip), fill=(219, 71, 54, 255), width=7)
        draw.rectangle((25, 52, 30, 59), fill=(31, 36, 47, 255))
        draw.rectangle((35, 52, 40, 59), fill=(31, 36, 47, 255))
        image.save(output / f"{name}.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets/paired-gaussian/fixture")
    args = parser.parse_args()
    make(args.output)
