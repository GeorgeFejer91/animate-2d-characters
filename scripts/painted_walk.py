"""Animate intact painted legs under a connected source garment.

Inputs are approved transparent source poses and measured landmarks. This does
not generate missing views or prove visual acceptance. Requires Pillow, NumPy,
SciPy; use the skill's final-frame analysis on the actual export.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates, label
from scipy.interpolate import PchipInterpolator
from harmonize_material import linear, srgb


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def premul(im):
    a = np.array(im.convert('RGBA'), dtype=float) / 255
    a[:, :, :3] = linear(a[:, :, :3]) * a[:, :, 3, None]
    return a


def unpack(a):
    alpha = np.clip(a[:, :, 3], 0, 1)
    rgb = np.divide(a[:, :, :3], alpha[:, :, None], out=np.zeros_like(a[:, :, :3]), where=alpha[:, :, None] > 1e-8)
    out = np.rint(np.dstack((np.clip(srgb(rgb), 0, 1), alpha)) * 255).astype('uint8')
    out[out[:, :, 3] < 20] = 0
    return Image.fromarray(out)


def sample(p, x, y):
    return np.stack([map_coordinates(p[:, :, i], np.stack((y, x)), order=1, mode='constant', cval=0, prefilter=False) for i in range(4)], axis=-1)


def register(im, height=432, baseline=480):
    """One source transform, then one fixed transform for the whole cycle."""
    rgba = im.convert('RGBA')
    alpha = np.array(rgba)[:, :, 3]
    bbox = Image.fromarray((alpha >= 32).astype('uint8') * 255).getbbox()
    if bbox is None or np.all(alpha >= 32):
        raise ValueError('Expected a nonempty transparent source pose')
    k = height / (bbox[3] - bbox[1])
    origin = np.array([256 - (bbox[0] + bbox[2]) / 2 * k, baseline - bbox[3] * k])
    yy, xx = np.mgrid[:round(im.height*k), :round(im.width*k)]
    scaled = unpack(sample(premul(rgba), xx/k, yy/k))
    source = Image.new('RGBA', (512, 512))
    source.alpha_composite(scaled, tuple(np.round(origin).astype(int)))
    return source, k, origin


def warp_layer(layer, ys, dxs, dys):
    dx = PchipInterpolator(ys, dxs, extrapolate=True)
    dy = PchipInterpolator(ys, dys, extrapolate=True)
    if min(1 + dy.derivative()(np.arange(layer.height))) <= .5:
        raise ValueError('Layer folds or compresses excessively; reduce stride')
    yy, xx = np.mgrid[:layer.height, :layer.width]
    sy = yy.astype(float)
    for _ in range(10):
        sy = yy - dy(np.clip(sy, 0, layer.height-1))
    sx = xx - dx(np.clip(sy, 0, layer.height-1))
    return unpack(sample(premul(layer), sx, sy))


def animate(source, c, travel=(1, 0), count=8, foreground=1, strength=1, phases=None, rigid_mask=None):
    """Landmarks use registered 512-square coordinates, left/right on screen.

    Roots remain under the original garment. The split follows transparent
    gaps rather than slicing feet at a fixed column. Foreground never changes
    with phase. Foot pixels below the ankle translate as one intact shape.
    """
    if source.size != (512, 512) or count < 4 or foreground not in (0, 1):
        raise ValueError('Expected 512-square source, >=4 frames and foreground 0/1')
    if not 0 <= strength <= 1:
        raise ValueError('Motion strength must be between zero and one')
    waist, hip, mid = c['waist'], c['hip'], c['mid']
    for side in range(2):
        if not 0 < waist < hip < c['hem'][side] < c['knee'][side] < c['ankle'][side] < 511:
            raise ValueError('Landmarks must follow waist, hip, hem, knee, ankle')
    numeric = [waist,hip,mid,*c['centres'],*c['hem'],*c['knee'],*c['ankle']]
    if len(c['centres']) != 2 or not np.all(np.isfinite(numeric)):
        raise ValueError('Expected finite measured pairs and scalar landmarks')
    if 'foot_centres' in c and (len(c['foot_centres']) != 2 or not 0 <= c['foot_centres'][0] < c['foot_centres'][1] < 512):
        raise ValueError('Foot centres must be an ordered measured source pair')
    if not 0 <= c.get('step_width',16) <= 64 or not 0 <= c.get('root_overlap',2) <= 32:
        raise ValueError('Stride/hidden-root overlap exceeds the supported range')
    if any(c['hem'][i]+c.get('root_overlap',2) >= c['knee'][i] for i in range(2)):
        raise ValueError('Root overlap must stay above both measured knees')
    if 'auto_hand_mask' in c and type(c['auto_hand_mask']) is not bool:
        raise ValueError('auto_hand_mask must be boolean')
    seam = c.get('split_path_xy')
    if seam and (len(seam)<2 or any(len(p)!=2 or not np.all(np.isfinite(p)) or not all(0<=z<512 for z in p) for p in seam) or any(b[1]<=a[1] for a,b in zip(seam,seam[1:]))):
        raise ValueError('Seam points must be finite source coordinates with increasing y')
    a = np.array(source)
    protected = None
    if rigid_mask is not None:
        if rigid_mask.size != source.size:
            raise ValueError('Rigid mask must use the registered source canvas')
        protected = np.array(rigid_mask.convert('L')) > 0
    leg_alpha = np.where(protected, 0, a[:, :, 3]) if protected is not None else a[:, :, 3]
    yy, xx = np.mgrid[:512, :512]
    split = np.full(512, mid)
    seam = c.get('split_path_xy')
    guide = PchipInterpolator([p[1] for p in seam], [p[0] for p in seam], extrapolate=False) if seam else None
    if guide is not None:
        split = guide(np.clip(np.arange(512), seam[0][1], seam[-1][1]))
    for y in range(round(min(c['hem'])), 512):
        seed = mid
        if 'foot_centres' in c:
            if y >= min(c['ankle']):
                split[y] = np.mean(c['foot_centres'])
                continue
            weight = np.clip((y-hip)/(min(c['ankle'])-hip), 0, 1)
            seed = mid*(1-weight) + np.mean(c['foot_centres'])*weight
            if guide is not None:
                seed = float(guide(np.clip(y,seam[0][1],seam[-1][1])))
            silhouette = np.flatnonzero(leg_alpha[y, :] >= 20)
            inside = (np.arange(512) > silhouette[0]) & (np.arange(512) < silhouette[-1]) if len(silhouette) else np.zeros(512, bool)
            candidates = np.flatnonzero((leg_alpha[y, :] < 20) & inside & (np.abs(np.arange(512)-seed) < 30))
            split[y] = seed
        else:
            candidates = np.flatnonzero((a[y, :, 3] < 20) & (np.abs(np.arange(512)-mid) < 30))
        if len(candidates):
            split[y] = float(candidates[np.argmin(np.abs(candidates-seed))])
    legs = []
    for side in range(2):
        own = xx < split[:, None] if side == 0 else xx >= split[:, None]
        layer = a.copy()
        layer[:, :, 3] = np.where((yy >= hip) & own, layer[:, :, 3], 0)
        legs.append(Image.fromarray(layer))
    hems = np.where(xx < mid, c['hem'][0], c['hem'][1])
    garment = a.copy()
    garment[:, :, 3] = np.where((yy >= waist-8) & (yy <= hems+c.get('root_overlap',2)), garment[:, :, 3], 0)
    upper = a.copy()
    upper[:, :, 3] = np.where(yy < hip+2, upper[:, :, 3], 0)
    outside = (xx < c['centres'][0]-42) | (xx > c['centres'][1]+42)
    hand = (yy < max(c['hem'])) & outside
    if c.get('auto_hand_mask') is False:
        hand = np.zeros_like(hand)
    upper[:, :, 3] = np.where(hand, a[:, :, 3], upper[:, :, 3])
    for side in range(2):
        pa = np.array(legs[side]); pa[hand] = 0; legs[side] = Image.fromarray(pa)
    if protected is not None:
        garment[protected, 3] = 0
        upper[protected, 3] = a[protected, 3]
        for side in range(2):
            pa = np.array(legs[side]); pa[protected, 3] = 0; legs[side] = Image.fromarray(pa)
    frames, records = [], []
    for col, phase in enumerate(phases if phases is not None else np.arange(count)*2*np.pi/count):
        vertical = abs(travel[1]) > 0
        bob = -(3.4 if vertical else 1.2)*np.cos(2*phase)*strength
        hip_shift = 3*np.sin(phase)*strength if vertical else 0
        canvas = Image.new('RGBA', (512, 512))
        moves = []
        for side in range(2):
            t = phase + side*np.pi
            base = (mid-c['foot_centres'][side])*strength if not vertical and 'foot_centres' in c else 0
            amplitude = c.get('step_width', 16)
            foot = base + travel[0]*amplitude*np.sin(t)*strength + (3*np.sin(t)*strength+hip_shift*.25 if vertical else 0)
            knee = base*.6 + travel[0]*(amplitude*7/16)*np.sin(t)*strength + (1.5*np.sin(t)*strength+hip_shift*.5 if vertical else 0)
            depth = travel[1]*9*np.sin(t)*strength
            lift = (14 if vertical else 7)*max(0, np.cos(t))*strength
            nodes = [0, waist, hip, c['hem'][side], c['knee'][side], c['ankle'][side], 511]
            dxs = [0, hip_shift, hip_shift, hip_shift+knee*.35, knee, foot, foot]
            dys = [bob, bob, bob, bob-lift*(.22 if vertical else .15)+depth*.22, bob-lift*(.55 if vertical else .4)+depth*.55, depth-lift, depth-lift]
            moves.append((nodes, dxs, dys, warp_layer(legs[side], nodes, dxs, dys)))
        for side in [1-foreground, foreground]:
            canvas.alpha_composite(moves[side][3])
        sy, sx = yy.astype(float)-bob, xx.astype(float)
        blend = np.clip((xx-mid+40)/80, 0, 1); blend = blend*blend*(3-2*blend)
        weight = np.clip((yy-waist)/max(hems.max()-waist, 1), 0, 1); weight = weight*weight*(3-2*weight)
        sx -= hip_shift+weight*((moves[0][1][3]-hip_shift)*(1-blend) + (moves[1][1][3]-hip_shift)*blend)
        if vertical:
            sy -= weight*((moves[0][2][3]-bob)*(1-blend) + (moves[1][2][3]-bob)*blend)
        canvas.alpha_composite(unpack(sample(premul(Image.fromarray(garment)), sx, sy)))
        canvas.alpha_composite(warp_layer(Image.fromarray(upper), [0,waist,511], [0,hip_shift,hip_shift], [bob,bob,bob]) if vertical else warp_layer(Image.fromarray(upper), [0,511], [0,0], [bob,bob]))
        if strength == 0:
            canvas = source.copy()
        labels, _ = label(np.array(canvas)[:, :, 3] >= 128)
        if sum(z >= 100 for z in np.bincount(labels.ravel())[1:]) != 1:
            error = ValueError('Detached painted region; inspect masks before exporting')
            error.frame = canvas; error.phase = col
            raise error
        frames.append(canvas)
        records.append({'phase': col, 'foreground_limb': 'viewer-right' if foreground == 1 else 'viewer-left', 'limb_displacement': [{'nodes_y':m[0], 'dx':m[1], 'dy':m[2]} for m in moves]})
    return frames, records


def plan_transition(source, target, walks, bridges, turn_cells, anchors, turn_ms=85, with_context=False):
    """Return runtime stop/body-turn/start cells; optionally add demo walks.

    Turn cells are ordered clockwise body poses, not gaze poses. Bridge stop
    frames end in the source's planted turn anchor; start frames lead into
    target walk phase0. Enter after the last source phase, then resume target
    phase0. The exporter must verify the planted endpoint pixels. A request
    for the current direction returns no core cells, preserving gait phase.
    with_context=True adds complete walk loops for export/demo review only.
    """
    def walk_cells(name):
        clip = walks[name]
        return [{'row':clip['row'], 'col':i, 'ms':clip['frame_ms']} for i in range(clip['count'])]
    if source == target:
        return walk_cells(source) if with_context else []
    count = len(turn_cells)
    start, end = anchors[source], anchors[target]
    if not count or not 0 <= start < count or not 0 <= end < count:
        raise ValueError('Turn anchors must address accepted body-pose cells')
    distance, sign = (end-start) % count, 1
    if distance > count/2:
        distance, sign = count-distance, -1
    path = [(start+sign*i) % count for i in range(1,distance+1)]
    stop, enter = bridges[source], bridges[target]
    core = ([{'row':stop['row'], 'col':i, 'ms':stop['frame_ms']} for i in stop['stop_cols']]
            + [{**turn_cells[i], 'ms':turn_ms} for i in path]
            + [{'row':enter['row'], 'col':i, 'ms':enter['frame_ms']} for i in enter['start_cols']])
    return walk_cells(source) + core + walk_cells(target) if with_context else core


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    base = args.spec.resolve().parent
    out = args.output_dir.resolve()
    size = tuple(spec.get('cell_size_xy', [192,208]))
    height = spec.get('figure_height', 160)
    baseline = spec.get('baseline_y', 203)
    count = spec.get('frame_count', 8)
    views = spec['views']
    ids = [v['id'] for v in views]
    if len(ids) != len(set(ids)) or any(not i or not all(ch.isalnum() or ch in '-_' for ch in i) for i in ids):
        raise ValueError('View IDs must be unique plain filenames')
    sources = {(base/v['file']).resolve() for v in views} | {(base/v['rigid_mask']).resolve() for v in views if v.get('rigid_mask')} | {args.spec.resolve()}
    targets = {out/'atlas.png', out/'animation.json'}
    for ident in ids:
        targets.add(out/(ident+'-source.png'))
        targets.update(out/f'{ident}-{col:02d}.png' for col in range(count))
    if targets & sources:
        raise ValueError('Output would overwrite an input source/spec; choose another directory')
    out.mkdir(parents=True, exist_ok=True)
    atlas = Image.new('RGBA', (size[0]*count, size[1]*len(views)))
    manifest = {'cell_size_xy':size, 'frame_ms':spec.get('frame_ms',120), 'pivot_xy':[size[0]/2,baseline], 'directions':[], 'method':'intact-painted-limbs', 'visual_acceptance':'pending actual export review'}
    for row, view in enumerate(views):
        file = (base/view['file']).resolve()
        source_hash = digest(file)
        if file == out/'atlas.png':
            raise ValueError('Output would overwrite source')
        working_baseline = view.get('working_baseline_y',470 if view.get('registered') or view['travel_xy'][1] else 480)
        if view.get('registered'):
            source=Image.open(file).convert('RGBA');k=1;origin=np.array([0,0])
            if source.size!=(512,512):raise ValueError('Registered source must be exactly 512-square')
        else:source,k,origin=register(Image.open(file),baseline=working_baseline)
        c = view['landmarks']
        mapped = {key: ([v*k+origin[1] for v in c[key]] if isinstance(c[key],list) else c[key]*k+origin[1]) for key in ('waist','hip','hem','knee','sock','ankle')}
        mapped['mid'] = c['mid']*k+origin[0]
        mapped['centres'] = [v*k+origin[0] for v in c['centres']]
        for key in ('step_width','root_overlap'):
            if key in c:mapped[key]=c[key]*k
        if 'auto_hand_mask' in c:mapped['auto_hand_mask']=c['auto_hand_mask']
        if 'foot_centres' in c:mapped['foot_centres']=[z*k+origin[0] for z in c['foot_centres']]
        if 'split_path_xy' in c:mapped['split_path_xy']=[[x*k+origin[0],y*k+origin[1]]for x,y in c['split_path_xy']]
        rigid=None
        if view.get('rigid_mask'):
            raw=Image.open(base/view['rigid_mask']).convert('L')
            if raw.size!=Image.open(file).size:raise ValueError('Mask must share the source dimensions')
            rigid=Image.new('L',(512,512));rigid.paste(raw.resize((round(raw.width*k),round(raw.height*k)),Image.Resampling.NEAREST),tuple(np.round(origin).astype(int)))
        world, motion = animate(source, mapped, view['travel_xy'], count, view.get('foreground',1),rigid_mask=rigid)
        source.save(out/(view['id']+'-source.png'))
        for col, im in enumerate(world):
            scale = height/432
            resized = im.resize((round(512*scale),round(512*scale)), Image.Resampling.LANCZOS)
            cell = Image.new('RGBA',size)
            cell.alpha_composite(resized,(round(size[0]/2-256*scale),round(baseline-working_baseline*scale)))
            bounds = cell.getbbox()
            if not bounds or bounds[0] == 0 or bounds[1] == 0 or bounds[2] == size[0] or bounds[3] == size[1]:
                raise ValueError('Clipped/padded edge; reduce family scale or reserve baseline space')
            cell.save(out/f"{view['id']}-{col:02d}.png")
            atlas.alpha_composite(cell,(col*size[0],row*size[1]))
        manifest['directions'].append({'id':view['id'],'row':row,'count':count,'source_file':str(file),'source_sha256':source_hash,'foreground':view.get('foreground',1),'motion':motion})
    atlas.save(out/'atlas.png')
    manifest['export_sha256'] = digest(out/'atlas.png')
    (out/'animation.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'atlas':str(out/'atlas.png'),'rows':len(views),'frames_per_row':count}))


if __name__ == '__main__':
    main()
