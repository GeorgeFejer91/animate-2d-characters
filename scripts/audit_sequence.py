"""Audit explicit frame order, silhouettes and annotated bone ranges; no anatomy inference."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import label


def audit(manifest, base):
    entries=manifest.get('frames',[])
    if not entries:raise ValueError('At least one ordered frame is required')
    threshold=int(manifest.get('alpha_threshold',32)); minimum=int(manifest.get('min_component_area',4))
    padding=int(manifest.get('padding',1));maximum=manifest.get('max_components')
    if not 1<=threshold<=255 or minimum<1 or padding<0 or (maximum is not None and int(maximum)<1):
        raise ValueError('Invalid alpha/component/padding policy')
    errors=[]; warnings=[]; records=[]; images=[]; size=None
    for i,e in enumerate(entries):
        path=base/e['file'];rgba=np.array(Image.open(path).convert('RGBA'));h,w=rgba.shape[:2]
        if size is None:size=(w,h)
        if size != (w,h):raise ValueError('Every frame must share one canvas')
        duration=e.get('duration_ms')
        if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:
            errors.append(f'Frame {i}: positive finite duration_ms required')
        visible=rgba[:,:,3]>=threshold;ys,xs=np.nonzero(visible)
        bounds=[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1] if len(xs) else None
        if bounds is None:errors.append(f'Frame {i}: blank artwork')
        elif min(bounds[0],bounds[1],w-bounds[2],h-bounds[3])<padding:
            errors.append(f'Frame {i}: artwork touches declared padding')
        character=visible.copy()
        if e.get('character_mask'):
            mask=Image.open(base/e['character_mask']).convert('L')
            if mask.size != size:raise ValueError('character_mask dimensions differ')
            character &= np.asarray(mask)>=128
        labels,_=label(character);areas=np.bincount(labels.ravel())[1:];areas=sorted((int(x) for x in areas if x>=minimum),reverse=True)
        if not areas:errors.append(f'Frame {i}: no character pixels after masking')
        if maximum is not None and len(areas)>int(maximum):errors.append(f'Frame {i}: {len(areas)} character components exceed {maximum}')
        limb_masks={}
        for name,file in e.get('limb_layers',{}).items():
            limb=Image.open(base/file).convert('RGBA')
            if limb.size!=size:raise ValueError('Limb layers must share the registered frame canvas')
            limb_masks[name]=np.asarray(limb)[:,:,3]>=threshold
            ll,_=label(limb_masks[name]);ls=np.bincount(ll.ravel())[1:];significant=[int(x) for x in ls if x>=minimum]
            if len(significant)!=1:errors.append(f'Frame {i}: limb {name} has {len(significant)} substantial components')
        attachments=[]
        for check in manifest.get('attachments',[]):
            joint=check['joint'];radius=float(check.get('radius',3));required=float(check.get('minimum_opaque_fraction',.95));joints=e.get('joints',{})
            if not math.isfinite(radius) or radius<=0 or not math.isfinite(required) or not 0<=required<=1:raise ValueError('Invalid attachment radius/fraction')
            if joint not in joints:errors.append(f'Frame {i}: missing attachment joint {joint}');continue
            point=joints[joint]
            if len(point)!=2 or not all(math.isfinite(x) for x in point):raise ValueError('Attachment joints need finite 2D coordinates')
            if check.get('layer'):
                if check['layer'] not in limb_masks:errors.append(f'Frame {i}: missing attachment layer {check["layer"]}');continue
                layer=limb_masks[check['layer']]
            else:layer=visible
            # Outside-canvas samples count as transparent rather than truncating
            # the disk and producing a false pass near a clipped joint.
            x0,y0=map(math.floor,(point[0]-radius,point[1]-radius));x1,y1=map(math.ceil,(point[0]+radius,point[1]+radius))
            yy,xx=np.mgrid[y0:y1+1,x0:x1+1];disk=(xx-point[0])**2+(yy-point[1])**2<=radius**2
            valid=(xx>=0)&(xx<w)&(yy>=0)&(yy<h);sample=np.zeros(disk.shape,dtype=bool);sample[valid]=layer[yy[valid],xx[valid]]
            fraction=float(sample[disk].mean());ok=fraction>=required
            if not ok:errors.append(f'Frame {i}: attachment {joint} opaque fraction {fraction:.3f} below {required}')
            attachments.append({'joint':joint,'layer':check.get('layer'),'opaque_fraction':fraction,'ok':ok})
        bones=[]
        for bone in manifest.get('bones',[]):
            joints=e.get('joints',{});a,b=bone['a'],bone['b']
            lo,hi=float(bone['min']),float(bone['max'])
            if not all(math.isfinite(x) for x in (lo,hi)) or not 0<=lo<=hi:raise ValueError('Invalid bone range')
            if a not in joints or b not in joints:
                errors.append(f'Frame {i}: missing joint {a} or {b}');continue
            coords=(*joints[a],*joints[b])
            if len(coords)!=4 or not all(math.isfinite(x) for x in coords):raise ValueError('Joints need finite 2D coordinates')
            distance=math.dist(joints[a],joints[b]);ok=lo<=distance<=hi
            if not ok:errors.append(f'Frame {i}: {a}-{b} length {distance:.3f} outside {lo}..{hi}')
            bones.append({'a':a,'b':b,'length':distance,'ok':ok})
        records.append({'frame':i,'file':e['file'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'duration_ms':duration,'bounds':bounds,'component_areas':areas,'bones':bones,'attachments':attachments})
        # Premultiplied RGB+alpha comparison ignores meaningless hidden RGB.
        z=rgba.astype(float)/255;z[:,:,:3]*=z[:,:,3,None];images.append(z)
    pairs=list(zip(range(len(images)-1),range(1,len(images))))
    if manifest.get('cyclic',True) and len(images)>1:pairs.append((len(images)-1,0))
    steps=[{'from':a,'to':b,'mean_difference':float(np.abs(images[a]-images[b]).mean())} for a,b in pairs]
    if len(steps)>2:
        median=float(np.median([z['mean_difference'] for z in steps]))
        for z in steps:
            if z['mean_difference']>max(.025,median*3):warnings.append(f"Large step {z['from']} -> {z['to']}; inspect for a visible pop")
    if len(images)>1 and all(z['mean_difference']==0 for z in steps):warnings.append('All frames identical; motion not demonstrated')
    return {'ok':not errors,'errors':errors,'warnings':warnings,'canvas':size,'frames':records,'steps':steps,
            'anatomy_assessed':'annotated bone/attachment constraints only' if manifest.get('bones') or manifest.get('attachments') else 'not assessed; no bone/attachment constraints supplied',
            'visual_review_required':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    cfg=json.loads(a.manifest.read_text());protected={a.manifest.resolve()}
    for entry in cfg.get('frames',[]):
        for key in ['file','character_mask']:
            if entry.get(key):protected.add((a.manifest.parent/entry[key]).resolve())
        protected.update((a.manifest.parent/path).resolve() for path in entry.get('limb_layers',{}).values())
    if a.report.resolve() in protected:p.error('Report cannot overwrite manifest, artwork, or masks')
    report=audit(cfg,a.manifest.parent)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__=='__main__':main()
