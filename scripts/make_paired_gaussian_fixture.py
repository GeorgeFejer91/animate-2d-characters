"""Regenerate the deliberately simple, unapproved synthetic correspondence fixture."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "assets/paired-gaussian/fixture"
OUT.mkdir(parents=True, exist_ok=True)

for name, tip in [("work", (51, 34)), ("bridge", (50, 20)), ("gesture", (44, 9))]:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((23, 24, 41, 54), fill=(37, 72, 117, 255))
    draw.ellipse((25, 8, 39, 23), fill=(227, 191, 146, 255))
    draw.line(((39, 29), tip), fill=(219, 71, 54, 255), width=7)
    draw.rectangle((25, 52, 30, 59), fill=(31, 36, 47, 255))
    draw.rectangle((35, 52, 40, 59), fill=(31, 36, 47, 255))
    image.save(OUT / f"{name}.png")
