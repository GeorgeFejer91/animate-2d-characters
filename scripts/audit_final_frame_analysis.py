"""Bind actual final-frame visual analysis to source art and encoded export.

This checks review completeness and provenance, not inferred visual quality.
The reviewer must inspect the decoded images before recording observations.
"""
from pathlib import Path
import argparse, hashlib, json, math
from PIL import Image
import numpy as np

CATEGORIES = ('identity', 'proportions', 'rendering_style', 'lighting_color',
              'contour', 'texture', 'anatomy_occlusion', 'motion')
ROLES = ('source_comparison', 'native', 'enlarged_light', 'enlarged_dark', 'ordered_motion')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    def constant(value):
        raise ValueError('Nonfinite JSON number: ' + value)
    return json.loads(Path(path).read_text(), parse_constant=constant)

def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Nonfinite number')
    if isinstance(value, dict):
        for v in value.values(): finite(v)
    if isinstance(value, list):
        for v in value: finite(v)

def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('Expected nonnegative integer')
    return value

def identifiers(values):
    if not values or any(not isinstance(v,str) or not v.strip() for v in values) or len(values)!=len(set(values)):
        raise ValueError('Identifiers must be unique nonempty strings')
    return values

def checked_image(record, base):
    path = (base / record['file']).resolve()
    if sha(path) != record['sha256']:
        raise ValueError('Stale image: ' + record['file'])
    with Image.open(path) as im:
        im.load()
        return im.convert('RGBA'), getattr(im, 'n_frames', 1)

def audit(manifest_path, review_path):
    errors = []
    base = Path(manifest_path).resolve().parent
    manifest, review = load(manifest_path), load(review_path)
    finite(manifest); finite(review)
    export, _ = checked_image(manifest['export'], base)
    cell_w, cell_h = [integer(v) for v in manifest['cell_size_xy']]
    if not cell_w or not cell_h:
        raise ValueError('Cell dimensions must be positive')
    expected = manifest['frames']
    ids = identifiers([f['id'] for f in expected])
    # Declare exactly the affected rows. A omitted final frame cannot be accepted.
    coverage = set()
    for row in manifest['movement_rows']:
        r, n = integer(row['row']), integer(row['count'])
        if not n or (r+1) * cell_h > export.height or n * cell_w > export.width:
            raise ValueError('Invalid movement row coverage')
        for col in range(n):
            if (r,col) in coverage: raise ValueError('Duplicate row coverage')
            coverage.add((r,col))
    declared = [(integer(f['row']), integer(f['col'])) for f in expected]
    if len(declared) != len(set(declared)) or set(declared) != coverage:
        raise ValueError('Review must cover every declared movement cell')
    references = manifest['references']
    reference_ids = identifiers([r['id'] for r in references])
    for ref in references: checked_image(ref, base)
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        raise ValueError('Named reviewer required')
    if review.get('export_sha256') != manifest['export']['sha256']:
        raise ValueError('Review targets a different export')
    if review.get('reference_sha256') != {r['id']:r['sha256'] for r in references}:
        raise ValueError('Review targets different canonical artwork')
    if review.get('ordered_motion_reviewed') is not True:
        raise ValueError('Ordered motion must actually be reviewed')
    reviewed = review['frames']
    review_ids = identifiers([f['id'] for f in reviewed])
    if len(review_ids) != len(set(review_ids)) or set(review_ids) != set(ids):
        raise ValueError('Missing, duplicate or unexpected frame analysis')
    byid = {f['id']: f for f in reviewed}
    for frame in expected:
        ident = frame['id']; item = byid[ident]
        identifiers(frame['reference_ids'])
        if not set(frame['reference_ids']).issubset(reference_ids):
            raise ValueError('Frame references unknown canonical artwork')
        pixels, _ = checked_image(frame, base)
        if pixels.size != (cell_w,cell_h):
            errors.append(ident + ': wrong frame dimensions')
        row, col = frame['row'], frame['col']
        target = export.crop((col*cell_w,row*cell_h,(col+1)*cell_w,(row+1)*cell_h))
        if not np.array_equal(np.array(pixels), np.array(target)):
            errors.append(ident + ': reviewed frame differs from final export')
        if item.get('sha256') != frame['sha256']:
            errors.append(ident + ': stale frame review')
        used = item.get('reference_ids', [])
        if not used or not set(used).issubset(reference_ids) or not set(frame['reference_ids']).issubset(used):
            errors.append(ident + ': canonical comparison missing')
        if item.get('verdict') != 'pass' or item.get('unresolved_findings') != []:
            errors.append(ident + ': failed or qualified visual acceptance')
        for category in CATEGORIES:
            finding = item.get('analysis', {}).get(category, {})
            if finding.get('status') != 'pass':
                errors.append(ident + ': ' + category + ' failed/unreviewed')
            observation = finding.get('observation')
            if not isinstance(observation, str) or len(observation.strip()) < 12:
                errors.append(ident + ': ' + category + ' needs an image-based observation')
        evidence = item.get('evidence', [])
        if set(e.get('role') for e in evidence) != set(ROLES):
            errors.append(ident + ': final-frame evidence roles incomplete')
        for entry in evidence:
            visual, count = checked_image(entry, base)
            role = entry['role']
            minimum = (cell_w,cell_h)
            if role in ('enlarged_light','enlarged_dark'): minimum=(cell_w*2,cell_h*2)
            if role == 'source_comparison':
                minimum=(cell_w*2,cell_h)
                if not set(frame['reference_ids']).issubset(entry.get('reference_ids', [])):
                    errors.append(ident + ': comparison evidence does not identify required references')
            if role == 'ordered_motion' and count == 1: minimum=(cell_w*2,cell_h)
            if visual.width < minimum[0] or visual.height < minimum[1]:
                errors.append(ident + ': ' + role + ' evidence too small')
    return {'ok':not errors, 'errors':errors, 'export_sha256':manifest['export']['sha256'],
            'frames_analyzed':len(reviewed), 'categories':list(CATEGORIES),
            'limitation':'Provenance and completeness gate; visual quality depends on actual image analysis.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest'); parser.add_argument('--review',required=True)
    parser.add_argument('--report',required=True); args=parser.parse_args()
    protected={Path(args.manifest).resolve(),Path(args.review).resolve()}
    try:
        manifest=load(args.manifest); review=load(args.review)
        base=Path(args.manifest).resolve().parent
        for record in [manifest['export'],*manifest['references'],*manifest['frames']]:
            protected.add((base/record['file']).resolve())
        for frame in review['frames']:
            for record in frame.get('evidence',[]): protected.add((base/record['file']).resolve())
        if Path(args.report).resolve() in protected:
            raise ValueError('Report cannot overwrite inputs or evidence')
    except (KeyError,TypeError,ValueError,OSError) as exc:
        # Never overwrite an unknown path if input parsing/protection failed.
        print(json.dumps({'ok':False,'errors':[str(exc)]})); return 1
    try:
        result=audit(args.manifest,args.review)
    except (KeyError,TypeError,ValueError,OSError,IndexError) as exc:
        result={'ok':False,'errors':[str(exc)]}
    Path(args.report).write_text(json.dumps(result,indent=2))
    print(json.dumps(result)); return 0 if result['ok'] else 1

if __name__=='__main__': raise SystemExit(main())
