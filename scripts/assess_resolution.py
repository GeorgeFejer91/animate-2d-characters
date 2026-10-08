"""Measure source/export/display sampling; dimensions do not certify visual quality."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tempfile
from PIL import Image


def positive(values, count):
    if not isinstance(values, (list, tuple)) or len(values) != count or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or
            not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('Positive finite dimensions/scale required')
    return values


def read_image(entry, base):
    path = (base / entry['file']).resolve()
    with Image.open(path) as opened:
        full = opened.convert('RGBA')
    region = entry.get('crop_xywh', [0, 0, full.width, full.height])
    if len(region) != 4 or any(type(v) is not int for v in region):
        raise ValueError('crop_xywh must contain four integers')
    x, y, w, h = region
    if min(x, y) < 0 or min(w, h) <= 0 or x + w > full.width or y + h > full.height:
        raise ValueError('Crop must fit wholly inside the image')
    image = full.crop((x, y, x + w, y + h)); bounds = image.getchannel('A').getbbox()
    if bounds is None: raise ValueError('Empty source/export crop')
    return image, bounds, {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                           'image_size_xy': list(full.size), 'crop_xywh': region}


def assess(spec, base=Path('.')):
    source, sb, source_info = read_image(spec['source'], base)
    cell, eb, export_info = read_image(spec['export'], base)
    css = positive(spec['display_css_size_xy'], 2)
    dpr = positive([spec.get('device_pixel_ratio', 1)], 1)[0]
    maximum = spec.get('max_texture_size', 4096)
    if type(maximum) is not int or maximum <= 0: raise ValueError('Positive integer texture limit required')
    mipmaps = spec.get('mipmaps', False)
    if type(mipmaps) is not bool: raise ValueError('mipmaps must be boolean')
    se = [sb[2] - sb[0], sb[3] - sb[1]]; ee = [eb[2] - eb[0], eb[3] - eb[1]]
    display = positive([css[i] * dpr for i in range(2)], 2)
    scale = [display[i] / cell.size[i] for i in range(2)]
    bake = [ee[i] / se[i] for i in range(2)]
    source_scale = [bake[i] * scale[i] for i in range(2)]
    aspect = abs(scale[0] / scale[1] - 1)
    gutter = min(eb[0], eb[1], cell.width - eb[2], cell.height - eb[3])
    fits = max(export_info['image_size_xy']) <= maximum
    warnings = []
    if max(bake) > 1.01: warnings.append('Export foreground exceeds source pixels. Compare corresponding poses; larger files do not create detail.')
    if max(scale) > 1.01: warnings.append('Display enlarges this cell. Prefer an adequate native-detail variant and inspect at the planned DPR.')
    if max(source_scale) > 1.01: warnings.append('Display exceeds source foreground detail. Obtain a better original or explicitly review the upscale; resizing cannot recover detail.')
    if aspect > .01: warnings.append('Unintended aspect stretch: display scales differ by more than one percent.')
    if not fits: warnings.append('Atlas exceeds the supplied texture limit.')
    if gutter == 0: warnings.append('No complete transparent gutter on at least one edge.')
    if source.getchannel('A').getextrema()[0] == 255: warnings.append('Opaque source crop: do not count padding or keyed backdrop as character pixels.')
    tw, th = export_info['image_size_xy']
    memory = tw * th * 4
    while mipmaps and (tw > 1 or th > 1):
        tw, th = max(1, tw // 2), max(1, th // 2)
        memory += tw * th * 4
    return {'source': source_info, 'export': export_info,
            'source_foreground_xy': se, 'export_foreground_xy': ee,
            'display_physical_size_xy': display, 'export_over_source_xy': bake,
            'display_over_export_xy': scale, 'display_over_source_foreground_xy': source_scale,
            'display_aspect_error': aspect, 'transparent_gutter_px': gutter,
            'max_texture_size': maximum, 'fits_texture_limit': fits,
            'estimated_rgba8_bytes': memory,
            'warnings': warnings, 'visual_review_required': True,
            'limitation': 'Dimensions and memory only; inspect identity, texture, alpha, anatomy and displayed sharpness.'}


def self_test():
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder); source = Image.new('RGBA', (100, 200))
        source.paste((80, 60, 40, 255), (10, 20, 90, 180)); source.save(base / 'source.png')
        source.resize((50, 100)).save(base / 'export.png')
        spec = {'source': {'file': 'source.png'}, 'export': {'file': 'export.png'},
                'display_css_size_xy': [50, 100], 'device_pixel_ratio': 2}
        result = assess(spec, base)
        assert result['display_over_export_xy'] == [2, 2]
        assert result['display_aspect_error'] == 0 and result['fits_texture_limit']
        assert result['estimated_rgba8_bytes'] == 20000 and result['warnings']
        assert result['transparent_gutter_px'] > 0
        spec['display_css_size_xy'] = [1e308, 1e308]
        try: assess(spec, base)
        except ValueError: pass
        else: raise AssertionError('Overflowing display dimensions accepted')
        spec['display_css_size_xy'] = [100, 100]
        assert assess(spec, base)['display_aspect_error'] == 1
        spec['max_texture_size'] = 64
        assert not assess(spec, base)['fits_texture_limit']
        spec['export']['crop_xywh'] = [0, 0, 51, 100]
        try: assess(spec, base)
        except ValueError: pass
        else: raise AssertionError('Out-of-bounds crop accepted')
        Image.new('RGBA', (64, 1), (80, 60, 40, 255)).save(base / 'thin.png')
        spec['export'] = {'file': 'thin.png'}
        spec['mipmaps'] = True
        assert assess(spec, base)['estimated_rgba8_bytes'] == 508
        for value in [0, -1, True, float('nan'), float('inf')]:
            try: positive([value], 1)
            except ValueError: pass
            else: raise AssertionError('Invalid scale accepted')
    print('PASS: DPR, sampling, aspect, texture budget, gutters and invalid inputs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', nargs='?', type=Path)
    parser.add_argument('--report', type=Path); parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test: self_test(); return
    if not args.manifest: parser.error('manifest required unless --self-test')
    result = assess(json.loads(args.manifest.read_text(encoding='utf-8')), args.manifest.resolve().parent)
    if args.report:
        protected = {args.manifest.resolve(), Path(result['source']['file']), Path(result['export']['file'])}
        if args.report.resolve() in protected: raise ValueError('Report cannot overwrite inputs')
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
