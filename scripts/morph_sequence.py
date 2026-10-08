"""Sample registered pose intervals; mesh validity does not establish anatomy.

CLI manifest: {"anchors": [{"file": "a.png", "points": [[0, 0], ...]},
...], "triangles": [[0, 1, 2], ...], "durations_ms": [120, ...],
"samples_per_interval": 4, "cyclic": false}. Counts may instead be a list.
Paths are relative to the manifest. Outputs must not already exist.

build_sequence returns (images, metadata). Timed samples are metadata['frames'];
each has an image_index. A one-shot also returns a final image referenced only
by metadata['terminal']: display it on completion, never as a zero-time loop
frame. Cycles sample the closing interval without duplicating the first pose.
All intervals evaluate the original anchors, never an earlier inbetween.
"""
import argparse
import hashlib
from io import BytesIO
import json
import math
from numbers import Integral, Real
from pathlib import Path

from PIL import Image
from morph_frames import morph


def png_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def build_sequence(images, points, triangles, durations_ms,
                   samples_per_interval=4, cyclic=False):
    """Return images and JSON-safe timing/provenance, with a separate terminal.

    A count n emits t=0, 1/n, ..., (n-1)/n for that interval. Its full duration
    is retained. All anchors must have the same canvas and corresponding mesh
    points. Crossings/visibility changes need approved keys or separate layers.
    """
    images = list(images)
    if len(images) < 2 or any(not isinstance(im, Image.Image) for im in images):
        raise ValueError('At least two Pillow anchor images required')
    if any(im.size != images[0].size for im in images) or min(images[0].size) < 2:
        raise ValueError('All anchors must share a canvas >=2x2')
    if not isinstance(cyclic, bool):
        raise ValueError('cyclic must be a boolean')
    if len(points) != len(images):
        raise ValueError('One corresponding landmark array per anchor required')
    intervals = len(images) if cyclic else len(images) - 1
    durations = list(durations_ms)
    if len(durations) != intervals or any(
            isinstance(d, bool) or not isinstance(d, Real) for d in durations):
        raise ValueError('One finite positive duration per interval required')
    try:
        durations = [float(d) for d in durations]
    except OverflowError as error:
        raise ValueError('Durations must be finite milliseconds') from error
    if any(not math.isfinite(d) or d <= 0 for d in durations):
        raise ValueError('One finite positive duration per interval required')
    if isinstance(samples_per_interval, Integral) and not isinstance(samples_per_interval, bool):
        counts = [int(samples_per_interval)] * intervals
    elif isinstance(samples_per_interval, (list, tuple)):
        counts = list(samples_per_interval)
    else:
        raise ValueError('samples_per_interval must be an integer or list of integers')
    if len(counts) != intervals or any(
            isinstance(n, bool) or not isinstance(n, Integral) or n < 1 for n in counts):
        raise ValueError('One positive integer sample count per interval required')
    counts = [int(n) for n in counts]
    try:
        total = math.fsum(durations)
    except OverflowError as error:
        raise ValueError('Total duration must be finite') from error
    if not math.isfinite(total):
        raise ValueError('Total duration must be finite')

    # Validate every endpoint, including the unsampled end of a closing interval.
    # morph also rejects folds anywhere along the interval, not just at samples.
    for i in range(intervals):
        j = (i + 1) % len(images)
        for t in (0, 1):
            morph(images[i], images[j], points[i], points[j], triangles, t)

    output = []
    records = []
    for i, (duration, count) in enumerate(zip(durations, counts)):
        j = (i + 1) % len(images)
        start = math.fsum(durations[:i])
        end = math.fsum(durations[:i + 1])
        for sample in range(count):
            t = sample / count
            at = start + duration * t
            until = end if sample == count - 1 else start + duration * ((sample + 1) / count)
            if until <= at:
                raise ValueError('Sample duration is too small for millisecond precision')
            frame = morph(images[i], images[j], points[i], points[j], triangles, t)
            index = len(output)
            output.append(frame)
            records.append({'image_index': index, 'file': f'{index:04d}.png',
                            'interval_index': i, 'source_index': i, 'target_index': j,
                            't': t, 'at_ms': at, 'duration_ms': until - at,
                            'anchor_index': i if sample == 0 else None,
                            'sha256': sha256(png_bytes(frame))})
    terminal = None
    if not cyclic:
        last = images[-1].convert('RGBA').copy()
        terminal = {'image_index': len(output), 'file': 'terminal.png',
                    'interval_index': intervals - 1, 'source_index': len(images) - 2,
                    'target_index': len(images) - 1, 'anchor_index': len(images) - 1,
                    't': 1.0, 'at_ms': total, 'sha256': sha256(png_bytes(last))}
        output.append(last)
    metadata = {'method': 'explicit-triangle-linear-light-premultiplied-alpha-morph',
                'canvas': list(images[0].size), 'cyclic': cyclic,
                'durations_ms': durations, 'samples_per_interval': counts,
                'total_duration_ms': total, 'frames': records, 'terminal': terminal,
                'anchors': [{'index': i, 'rgba_sha256': sha256(im.convert('RGBA').tobytes())}
                            for i, im in enumerate(images)],
                'endpoint_pixels_preserved': True, 'anatomy_assessed': False,
                'visual_review_required': True}
    return output, metadata


def export_manifest(manifest, output_dir):
    """Read PNG anchors and write a fresh sequence only after full validation."""
    manifest = Path(manifest).resolve()
    output_dir = Path(output_dir).resolve()
    manifest_bytes = manifest.read_bytes()
    cfg = json.loads(manifest_bytes)
    paths = [(manifest.parent / anchor['file']).resolve() for anchor in cfg['anchors']]
    images = []
    for path in paths:
        with Image.open(path) as image:
            if image.format != 'PNG':
                raise ValueError('Anchor files must be PNG images')
            images.append(image.convert('RGBA'))
    frames, metadata = build_sequence(
        images, [anchor['points'] for anchor in cfg['anchors']], cfg['triangles'],
        cfg['durations_ms'], cfg.get('samples_per_interval', 4), cfg.get('cyclic', False))
    records = metadata['frames'] + ([metadata['terminal']] if metadata['terminal'] else [])
    outputs = [output_dir / record['file'] for record in records]
    sequence_path = output_dir / 'sequence.json'
    protected = {manifest, *paths}
    for path in [*outputs, sequence_path]:
        if path.resolve() in protected:
            raise ValueError('Output cannot overwrite an anchor or input manifest')
        if path.exists() or path.is_symlink():
            raise FileExistsError(f'Output already exists: {path}')
    metadata['source_manifest_sha256'] = sha256(manifest_bytes)
    for anchor, path in zip(metadata['anchors'], paths):
        anchor.update({'file': str(path), 'sha256': sha256(path.read_bytes())})
    # No output directory or file is created until validation and collision checks pass.
    output_dir.mkdir(parents=True, exist_ok=True)
    for frame_path, record in zip(outputs, records):
        with frame_path.open('xb') as stream:
            stream.write(png_bytes(frames[record['image_index']]))
    with sequence_path.open('x', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    metadata = export_manifest(args.manifest, args.output_dir)
    print(json.dumps({'ok': True, 'frames': len(metadata['frames']),
                      'terminal': metadata['terminal'] is not None,
                      'total_duration_ms': metadata['total_duration_ms'],
                      'sequence': str(args.output_dir / 'sequence.json'),
                      'visual_review_required': True}, indent=2))


if __name__ == '__main__':
    main()
