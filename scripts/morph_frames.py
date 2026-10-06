"""Explicit-mesh image interpolation; valid mapping is not anatomical correctness."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates
from harmonize_material import linear,srgb


def area(points):
    a,b,c=points
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def validate_mesh(a,b,triangles):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    if a.ndim!=2 or a.shape[1]!=2 or a.shape!=b.shape or len(a)<3 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Matching finite Nx2 landmark arrays required')
    tri=np.asarray(triangles)
    if tri.ndim!=2 or tri.shape[1]!=3 or len(tri)==0 or not np.issubdtype(tri.dtype,np.integer) or tri.min()<0 or tri.max()>=len(a):
        raise ValueError('Triangles must be nonempty index triples in landmark range')
    if len({tuple(sorted(t)) for t in tri})!=len(tri):raise ValueError('Duplicate triangle')
    # Each determinant is quadratic in t; check endpoints and its exact extremum.
    for i,t in enumerate(tri):
        d0=area(a[t]);d1=area(b[t]);dm=area((a[t]+b[t])/2)
        qa=2*(d1+d0-2*dm);qb=d1-d0-qa
        candidates=[d0,d1]
        if abs(qa)>1e-12:
            root=-qb/(2*qa)
            if 0<root<1:candidates.append(qa*root*root+qb*root+d0)
        sign=1 if d0>0 else -1
        if min(sign*x for x in candidates)<=1e-7:
            raise ValueError(f'Triangle {i} degenerates or flips over the transition')
    return a,b,tri


def coordinate_maps(a,b,tri,t,size):
    w,h=size; mid=a*(1-t)+b*t
    yy,xx=np.mgrid[:h,:w];pixels=np.stack((xx,yy,np.ones_like(xx)),axis=-1).reshape(-1,3)
    owners=np.full(w*h,-1);interiors=np.zeros(w*h,dtype=int)
    src=np.zeros((w*h,2));dst=np.zeros_like(src)
    for i,indices in enumerate(tri):
        verts=mid[indices];matrix=np.vstack((verts.T,np.ones(3)))
        weights=pixels @ np.linalg.inv(matrix).T
        inside=(weights>=-1e-7).all(axis=1)
        interiors+=(weights>1e-7).all(axis=1)
        selected=inside&(owners<0);owners[selected]=i
        src[selected]=weights[selected] @ a[indices];dst[selected]=weights[selected] @ b[indices]
    if np.any(owners<0):raise ValueError(f'Mesh leaves {int((owners<0).sum())} canvas pixels uncovered at t={t:.4f}')
    if np.any(interiors>1):raise ValueError(f'Mesh overlaps pixel interiors at t={t:.4f}')
    # Tiny round-off at frame corners must not select constant padding.
    for mapping in (src,dst):
        mapping[:,0]=np.clip(mapping[:,0],0,w-1);mapping[:,1]=np.clip(mapping[:,1],0,h-1)
    return src.reshape(h,w,2),dst.reshape(h,w,2)


def premultiplied(im):
    rgba=np.asarray(im.convert('RGBA'),dtype=float)/255
    rgba[:,:,:3]=linear(rgba[:,:,:3])*rgba[:,:,3,None]
    return rgba


def sample(im,coords):
    yx=np.stack((coords[:,:,1],coords[:,:,0]))
    return np.stack([map_coordinates(im[:,:,c],yx,order=1,mode='nearest',prefilter=False) for c in range(4)],axis=-1)


def morph(source,target,a,b,tri,t):
    if source.size!=target.size or min(source.size)<2:raise ValueError('Same canvas >=2x2 required')
    if not 0<=t<=1:raise ValueError('Interpolation t must be 0..1')
    a,b,tri=validate_mesh(a,b,tri)
    if np.any(a<0) or np.any(b<0) or np.any(a>np.array(source.size)-1) or np.any(b>np.array(source.size)-1):
        raise ValueError('Landmarks must be inside the pixel-centre canvas')
    sa,sb=coordinate_maps(a,b,tri,t,source.size)
    if t==0:return source.convert('RGBA').copy()
    if t==1:return target.convert('RGBA').copy()
    warped=sample(premultiplied(source),sa)*(1-t)+sample(premultiplied(target),sb)*t
    alpha=warped[:,:,3];rgb=np.divide(warped[:,:,:3],alpha[:,:,None],out=np.zeros_like(warped[:,:,:3]),where=alpha[:,:,None]>1e-10)
    rgba=np.dstack((np.clip(srgb(rgb),0,1),np.clip(alpha,0,1)))
    out=np.rint(rgba*255).astype('uint8');out[out[:,:,3]==0,:3]=0
    return Image.fromarray(out)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path)
    p.add_argument('--steps',type=int,default=5);p.add_argument('--duration-ms',type=int,default=40)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    if args.steps<2 or args.duration_ms<=0:p.error('steps >=2 and positive duration required')
    cfg=json.loads(args.manifest.read_text());base=args.manifest.parent
    source=Image.open(base/cfg['source']).convert('RGBA');target=Image.open(base/cfg['target']).convert('RGBA')
    a,b,tri=validate_mesh(cfg['points_source'],cfg['points_target'],cfg['triangles'])
    frames=[morph(source,target,a,b,tri,float(t)) for t in np.linspace(0,1,args.steps)]
    paths=[args.output_dir/f'{i:03d}.png' for i in range(len(frames))]
    protected={(base/cfg['source']).resolve(),(base/cfg['target']).resolve(),args.manifest.resolve()}
    sequence_path=args.output_dir/'sequence.json'
    if any(path.resolve() in protected for path in [*paths,sequence_path,args.report]) or args.report.resolve() in {path.resolve() for path in [*paths,sequence_path]}:
        raise ValueError('Output cannot overwrite approved endpoints')
    args.output_dir.mkdir(parents=True,exist_ok=True);entries=[]
    for i,(frame,path) in enumerate(zip(frames,paths)):
        frame.save(path);entries.append({'file':path.name,'duration_ms':args.duration_ms,'t':i/(args.steps-1),
                                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (args.output_dir/'sequence.json').write_text(json.dumps({'frames':entries,'cyclic':False},indent=2))
    report={'ok':True,'method':'explicit-triangle-linear-light-premultiplied-alpha-morph',
            'canvas':source.size,'triangles':len(tri),'frames':entries,
            'source_sha256':hashlib.sha256((base/cfg['source']).read_bytes()).hexdigest(),
            'target_sha256':hashlib.sha256((base/cfg['target']).read_bytes()).hexdigest(),
            'endpoint_pixels_preserved':True,'anatomy_assessed':False,'visual_review_required':True}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
