"""Match an explicitly masked material to a reference without changing alpha."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

M1 = np.array([[.4122214708,.5363325363,.0514459929],
               [.2119034982,.6806995451,.1073969566],
               [.0883024619,.2817188376,.6299787005]])
M2 = np.array([[.2104542553,.7936177850,-.0040720468],
               [1.9779984951,-2.4285922050,.4505937099],
               [.0259040371,.7827717662,-.8086757660]])


def linear(rgb):
    return np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)


def srgb(rgb):
    return np.where(rgb <= .0031308, 12.92*rgb, 1.055*np.maximum(rgb,0)**(1/2.4)-.055)


def oklab(rgb):
    return np.cbrt(linear(rgb) @ M1.T) @ M2.T


def from_oklab(lab):
    return srgb((lab @ np.linalg.inv(M2).T)**3 @ np.linalg.inv(M1).T)


def mask_for(path, rgba):
    im = Image.open(path).convert('L')
    if im.size != (rgba.shape[1],rgba.shape[0]):
        raise ValueError('Mask dimensions must match their image')
    return np.asarray(im,dtype=float)/255


def harmonize(source, source_mask, reference, reference_mask, strength=1., lightness_limit=.08, chroma_limit=.08):
    if not 0 <= strength <= 1 or min(lightness_limit,chroma_limit) < 0:
        raise ValueError('Strength must be 0..1 and limits nonnegative')
    s=np.array(source.convert('RGBA')); r=np.array(reference.convert('RGBA'))
    sm=np.asarray(source_mask,dtype=float); rm=np.asarray(reference_mask,dtype=float)
    if sm.shape != s.shape[:2] or rm.shape != r.shape[:2] or not np.all(np.isfinite(sm)) or not np.all(np.isfinite(rm)):
        raise ValueError('Masks must be finite and match source/reference')
    if np.any(sm<0) or np.any(sm>1) or np.any(rm<0) or np.any(rm>1):
        raise ValueError('Mask weights must be 0..1')
    sp=(sm>=.5)&(s[:,:,3]>=192); rp=(rm>=.5)&(r[:,:,3]>=192)
    if min(int(sp.sum()),int(rp.sum())) < 16:
        raise ValueError('Each material needs at least 16 opaque masked sample pixels')
    sl=oklab(s[:,:,:3]/255); rl=oklab(r[:,:,:3]/255)
    before=np.median(sl[sp],axis=0); target=np.median(rl[rp],axis=0)
    delta=target-before; delta[0]=np.clip(delta[0],-lightness_limit,lightness_limit)
    norm=np.linalg.norm(delta[1:]); delta[1:] *= min(1,chroma_limit/max(norm,1e-12))
    weight=sm*strength
    lab=sl+weight[:,:,None]*delta
    # Preserve lightness and compress out-of-gamut chroma rather than clipping
    # channels into flat, saturated highlights.
    lightness_clipped=(lab[:,:,0]<0)|(lab[:,:,0]>1)
    lab[:,:,0]=np.clip(lab[:,:,0],0,1)
    candidate=from_oklab(lab)
    outside=np.any((candidate < -1e-8)|(candidate > 1+1e-8),axis=2)
    low=np.zeros(sm.shape);high=np.ones(sm.shape)
    for _ in range(16):
        middle=(low+high)/2; trial=lab.copy();trial[:,:,1:]*=middle[:,:,None]
        trial_rgb=from_oklab(trial);valid=np.all((trial_rgb>=-1e-8)&(trial_rgb<=1+1e-8),axis=2)
        low=np.where(valid,middle,low);high=np.where(valid,high,middle)
    lab[:,:,1:]*=np.where(outside,low,1)[:,:,None]
    candidate=from_oklab(lab)
    selected=(sm>0)&(s[:,:,3]>0)
    out=s.copy(); out[selected,:3]=np.rint(np.clip(candidate[selected],0,1)*255).astype('uint8')
    # Preserve unselected pixels exactly; callers perform final alpha-zero RGB cleanup.
    after=np.median(oklab(out[:,:,:3]/255)[sp],axis=0)
    return Image.fromarray(out), {'source_samples':int(sp.sum()),'reference_samples':int(rp.sum()),
      'median_before':before.tolist(),'median_reference':target.tolist(),'median_after':after.tolist(),
      'delta_applied':(delta*strength).tolist(),'distance_before':float(np.linalg.norm(before-target)),
      'distance_after':float(np.linalg.norm(after-target)),
      'gamut_compressed_selected_fraction':float(outside[selected].mean()),
      'lightness_clamped_selected_fraction':float(lightness_clipped[selected].mean()),
      'clipped_selected_fraction':float(np.any((candidate[selected]<0)|(candidate[selected]>1),axis=1).mean()),
      'alpha_unchanged':bool(np.array_equal(out[:,:,3],s[:,:,3]))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['source','mask','reference','reference-mask','output','report']:
        p.add_argument('--'+key,required=True,type=Path)
    p.add_argument('--strength',type=float,default=1.)
    p.add_argument('--lightness-limit',type=float,default=.08)
    p.add_argument('--chroma-limit',type=float,default=.08)
    a=p.parse_args()
    protected={x.resolve() for x in [a.source,a.mask,a.reference,a.reference_mask]}
    if a.output.resolve() in protected or a.report.resolve() in protected or a.output.resolve()==a.report.resolve():
        p.error('Output/report must be distinct and cannot overwrite source, reference, or masks')
    input_hashes={k:hashlib.sha256(path.read_bytes()).hexdigest() for k,path in [('source',a.source),('reference',a.reference),('source_mask',a.mask),('reference_mask',a.reference_mask)]}
    s=Image.open(a.source).convert('RGBA'); r=Image.open(a.reference).convert('RGBA')
    im,report=harmonize(s,mask_for(a.mask,np.asarray(s)),r,mask_for(a.reference_mask,np.asarray(r)),a.strength,a.lightness_limit,a.chroma_limit)
    a.output.parent.mkdir(parents=True,exist_ok=True); im.save(a.output)
    report.update({key+'_sha256':value for key,value in input_hashes.items()})
    report['output_sha256']=hashlib.sha256(a.output.read_bytes()).hexdigest()
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
