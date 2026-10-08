"""Run small synthetic sequence tests; these do not assess character anatomy."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw
from morph_frames import morph
from morph_sequence import build_sequence, export_manifest


def rejected(call, error=ValueError):
    try:
        call()
    except error:
        return
    raise AssertionError(f'Expected {error.__name__}')


def main():
    tests = []
    images = []
    points = []
    triangles = [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]]
    for x, y in [(7, 7), (9, 6), (6, 9)]:
        image = Image.new('RGBA', (16, 16), (0, 255, 255, 0))
        ImageDraw.Draw(image).rectangle((x - 2, y - 2, x + 2, y + 2), fill=(220, 40, 30, 255))
        images.append(image)
        points.append([[0, 0], [15, 0], [15, 15], [0, 15], [x, y]])

    frames, report = build_sequence(images, points, triangles, [90, 210], [3, 7])
    assert len(frames) == 11 and len(report['frames']) == 10
    assert all(record['duration_ms'] > 0 for record in report['frames'])
    assert math.isclose(sum(record['duration_ms'] for record in report['frames']), 300)
    assert report['total_duration_ms'] == 300
    assert report['terminal']['at_ms'] == 300 and 'duration_ms' not in report['terminal']
    for anchor, index in zip(images, [0, 3, 10]):
        assert np.array_equal(frames[index], anchor), 'Anchor pixels changed'
    assert [r['anchor_index'] for r in report['frames'] if r['anchor_index'] is not None] == [0, 1]
    assert report['terminal']['anchor_index'] == 2
    assert report['frames'][3]['at_ms'] == 90
    tests.append('one-shot exact anchors, distinct shared boundaries, separate terminal, unchanged duration')

    loop, cycle = build_sequence(images, points, triangles, [90, 210, 120], [3, 7, 4], True)
    assert len(loop) == len(cycle['frames']) == 14 and cycle['terminal'] is None
    assert math.isclose(sum(r['duration_ms'] for r in cycle['frames']), 420)
    assert [(r['source_index'], r['target_index']) for r in cycle['frames']][-1] == (2, 0)
    assert cycle['frames'][-1]['t'] == .75 and cycle['frames'][-1]['at_ms'] == 390
    assert all(r['t'] < 1 for r in cycle['frames'])
    assert [r['anchor_index'] for r in cycle['frames'] if r['anchor_index'] is not None] == [0, 1, 2]
    expected = morph(images[2], images[0], points[2], points[0], triangles, .75)
    assert np.array_equal(loop[-1], expected), 'Closing interval was not rendered'
    for index, anchor in zip([0, 3, 10], images):
        assert np.array_equal(loop[index], anchor)
    tests.append('cyclic closing interval rendered with exact anchors and no duplicate first endpoint')

    # Endpoint-only samples still need continuous fold checks on the closing pair.
    # Two 90-degree corner rotations stay oriented; a direct 180-degree return
    # collapses at its midpoint and must fail even when that midpoint is unsampled.
    corners = np.array([[0, 0], [15, 0], [15, 15], [0, 15]])
    rotated = [np.roll(corners, i, axis=0) for i in range(3)]
    corner_triangles = [[0, 1, 2], [0, 2, 3]]
    build_sequence(images, rotated, corner_triangles, [1, 1], 1)
    rejected(lambda: build_sequence(images, rotated, corner_triangles, [1, 1, 1], 1, True))
    tests.append('unsampled folding closing interval rejected after valid open endpoint samples')

    for image, record in zip(loop, cycle['frames']):
        if record['t'] == 0:
            continue
        rgba = np.asarray(image)
        assert np.all(rgba[rgba[:, :, 3] == 0, :3] == 0)
        assert np.all(np.abs(rgba[rgba[:, :, 3] > 0, :3].astype(int) - [220, 40, 30]) <= 1)
    tests.append('intermediate alpha-zero RGB cleared and hidden cyan does not bleed into red material')

    once, low = build_sequence(images, points, triangles, [1, 2], 1)
    dense, high = build_sequence(images, points, triangles, [1, 2], 13)
    assert len(once) == 3 and len(dense) == 27
    assert low['total_duration_ms'] == high['total_duration_ms'] == 3
    assert math.isclose(math.fsum(r['duration_ms'] for r in high['frames']), 3)
    assert high['frames'][13]['at_ms'] == 1
    again, repeat = build_sequence(images, points, triangles, [1, 2], 13)
    assert high == repeat and all(np.array_equal(a, b) for a, b in zip(dense, again))
    tests.append('frame count can increase independently of cadence; repeated rendering is deterministic')

    for durations in [[0, 1], [-1, 1], [float('nan'), 1], [float('inf'), 1],
                      [True, 1], ['1', 1], [1], [1e308, 1e308], [10**400, 1]]:
        rejected(lambda: build_sequence(images, points, triangles, durations))
    for count in [0, -1, True, 1.5, [1], [1, False], [1, 1.5], [1, -2]]:
        rejected(lambda: build_sequence(images, points, triangles, [1, 1], count))
    rejected(lambda: build_sequence(images, points, triangles, [5e-324, 1], 2))
    rejected(lambda: build_sequence(images, points, triangles, [1e20, 1], 1))
    rejected(lambda: build_sequence(images, points, triangles, [1, 1], cyclic='false'))
    rejected(lambda: build_sequence(images[:1], points[:1], triangles, []))
    rejected(lambda: build_sequence([*images[:2], Image.new('RGBA', (8, 8))], points, triangles, [1, 1]))
    rejected(lambda: build_sequence(images, points[:2], triangles, [1, 1]))
    for invalid in [[[0, 1, 4]], [[0, 1, 4], [0, 1, 4]], [[0, 1, 9]], [[0, 1, -1]], [[0.0, 1, 2]]]:
        rejected(lambda: build_sequence(images, points, invalid, [1, 1]))
    # A complete mesh plus a different large triangle overlaps interiors;
    # this exercises coverage ownership rather than duplicate-index rejection.
    rejected(lambda: build_sequence(images, points, triangles + [[0, 1, 2]], [1, 1]))
    flipped = copy.deepcopy(points)
    flipped[1][0], flipped[1][1] = flipped[1][1], flipped[1][0]
    rejected(lambda: build_sequence(images, flipped, triangles, [1, 1]))
    outside = copy.deepcopy(points)
    outside[1][4] = [16, 7]
    rejected(lambda: build_sequence(images, outside, triangles, [1, 1]))
    tests.append('invalid durations/precision, counts, canvas, correspondence, coverage/overlap, indices and folds rejected')

    with tempfile.TemporaryDirectory(prefix='morph-sequence-test-') as temporary:
        base = Path(temporary)
        anchors = []
        for index, (image, landmark) in enumerate(zip(images, points)):
            name = f'anchor-{index}.png'
            image.save(base / name)
            anchors.append({'file': name, 'points': landmark})
        cfg = {'anchors': anchors, 'triangles': triangles, 'durations_ms': [90, 210],
               'samples_per_interval': [3, 7], 'cyclic': False}
        manifest = base / 'input.json'
        manifest.write_text(json.dumps(cfg), encoding='utf-8')
        input_bytes = {p: p.read_bytes() for p in [manifest, *(base / a['file'] for a in anchors)]}
        first = export_manifest(manifest, base / 'first')
        second = export_manifest(manifest, base / 'second')
        assert first == second
        for record in [*first['frames'], first['terminal']]:
            encoded = (base / 'first' / record['file']).read_bytes()
            assert hashlib.sha256(encoded).hexdigest() == record['sha256']
            assert encoded == (base / 'second' / record['file']).read_bytes()
            with Image.open(base / 'first' / record['file']) as decoded:
                assert np.array_equal(decoded, frames[record['image_index']])
        assert (base / 'first' / 'sequence.json').read_bytes() == (base / 'second' / 'sequence.json').read_bytes()
        assert first['source_manifest_sha256'] == hashlib.sha256(input_bytes[manifest]).hexdigest()
        tests.append('PNG hashes, decoded anchor fidelity, source provenance and deterministic manifest export')

        # Even when a later output collides, no earlier frame may have been written.
        collision = base / 'collision'
        collision.mkdir()
        protected_png = collision / '0009.png'
        images[0].save(protected_png)
        original = protected_png.read_bytes()
        conflicting = copy.deepcopy(cfg)
        conflicting['anchors'][0]['file'] = 'collision/0009.png'
        manifest.write_text(json.dumps(conflicting), encoding='utf-8')
        rejected(lambda: export_manifest(manifest, collision))
        assert list(collision.iterdir()) == [protected_png] and protected_png.read_bytes() == original

        manifest_collision = base / 'manifest-collision'
        manifest_collision.mkdir()
        collision_cfg = copy.deepcopy(cfg)
        for anchor in collision_cfg['anchors']:
            anchor['file'] = '../' + anchor['file']
        protected_manifest = manifest_collision / 'sequence.json'
        protected_manifest.write_text(json.dumps(collision_cfg), encoding='utf-8')
        original_manifest = protected_manifest.read_bytes()
        rejected(lambda: export_manifest(protected_manifest, manifest_collision))
        assert list(manifest_collision.iterdir()) == [protected_manifest]
        assert protected_manifest.read_bytes() == original_manifest
        manifest.write_bytes(input_bytes[manifest])
        existing = (base / 'first' / '0000.png').read_bytes()
        rejected(lambda: export_manifest(manifest, base / 'first'), FileExistsError)
        assert (base / 'first' / '0000.png').read_bytes() == existing
        assert all(path.read_bytes() == content for path, content in input_bytes.items())
        tests.append('all collisions checked before writes; anchors, input manifest and existing exports protected')

        malformed = copy.deepcopy(cfg)
        malformed['triangles'] = [[0, 1, 4]]
        manifest.write_text(json.dumps(malformed), encoding='utf-8')
        rejected(lambda: export_manifest(manifest, base / 'invalid'))
        assert not (base / 'invalid').exists()
        manifest.write_bytes(input_bytes[manifest])
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('morph_sequence.py')),
                                 str(manifest), '--output-dir', str(base / 'cli')],
                                capture_output=True, text=True, check=True)
        cli = json.loads(result.stdout)
        assert cli['ok'] and cli['frames'] == 10 and cli['terminal'] and cli['total_duration_ms'] == 300
        assert json.loads((base / 'cli' / 'sequence.json').read_text()) == first
        tests.append('invalid topology creates no output directory; CLI round trip matches Python API export')
    print(json.dumps({'ok': True, 'tests': tests, 'anatomy_assessed': False}, indent=2))


if __name__ == '__main__':
    main()
