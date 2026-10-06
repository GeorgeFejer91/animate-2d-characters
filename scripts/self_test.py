from pathlib import Path
import sys,json,tempfile,math
import numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_math import solve_two_bone,walk_phase
from harmonize_material import harmonize,oklab,from_oklab
from morph_frames import morph,validate_mesh
from audit_sequence import audit
tests=[]
for sign in [-1,1]:
 for root,target,u,l in [((0,0),(30,80),60,50),((0,0),(0,0),40,40),((3,5),(3,5),60,30),((0,0),(0,150),40,30)]:
  result=solve_two_bone(root,target,u,l,sign)
  assert abs(result['upper_length']-u)<1e-7 and abs(result['lower_length']-l)<1e-7
assert solve_two_bone((0,0),(0,150),40,30)['reach_error']==80
for p in np.linspace(0,1,32,endpoint=False):
 c=walk_phase(float(p));assert c['left']['stance']!=c['right']['stance']
tests.append('IK reachable/unreachable/folded geometry and alternating stance')
rng=np.random.default_rng(41);rgb=rng.random((8,8,3));assert np.max(abs(from_oklab(oklab(rgb))-rgb))<1e-6
s=Image.new('RGBA',(32,32),(170,125,90,255));r=Image.new('RGBA',(32,32),(195,155,115,255))
mask=np.zeros((32,32));mask[4:28,4:28]=1
matched,report=harmonize(s,mask,r,np.ones((32,32)))
assert report['distance_after']<report['distance_before'] and report['alpha_unchanged']
assert np.array_equal(np.array(matched)[0],np.array(s)[0])
tests.append('material match reduces palette difference, preserves alpha/unmasked pixels')
a=np.array([[0,0],[31,0],[31,31],[0,31],[16,16]]);b=a.copy();b[4]=[18,15];tri=[[0,1,4],[1,2,4],[2,3,4],[3,0,4]]
src=Image.new('RGBA',(32,32));ImageDraw.Draw(src).rectangle((9,9,22,22),fill=(255,20,30,255))
dst=src.copy();mid=morph(src,dst,a,b,tri,.5)
assert np.array_equal(np.asarray(morph(src,dst,a,b,tri,0)),np.asarray(src))
assert np.array_equal(np.asarray(morph(src,dst,a,b,tri,1)),np.asarray(dst))
out=np.asarray(mid);assert np.all(out[out[:,:,3]==0,:3]==0)
for bad in [a[[1,0,2,3,4]],np.array([[0,0],[31,0],[31,31],[0,31],[31,0]])]:
 try:validate_mesh(a,bad,tri)
 except ValueError:pass
 else:raise AssertionError('invalid morph topology accepted')
try:morph(src,dst,a,b,[[0,1,4]],.5)
except ValueError:pass
else:raise AssertionError('incomplete mesh accepted')
tests.append('morph endpoint fidelity, clean alpha, flip/degeneracy/coverage rejection')
with tempfile.TemporaryDirectory() as tmp:
 base=Path(tmp);src.save(base/'0.png');dst.save(base/'1.png')
 cfg={'frames':[{'file':'0.png','duration_ms':100,'joints':{'a':[9,9],'b':[9,22]}},{'file':'1.png','duration_ms':100,'joints':{'a':[9,9],'b':[9,22]}}],'bones':[{'a':'a','b':'b','min':12,'max':14}],'max_components':1}
 assert audit(cfg,base)['ok']
 broken=dst.copy();ImageDraw.Draw(broken).rectangle((26,26,29,29),fill=(255,0,0,255));broken.save(base/'1.png');assert not audit(cfg,base)['ok']
 cfg['frames'][1]['joints']['b']=[9,29];assert any('length' in e for e in audit(cfg,base)['errors'])
 src.save(base/'1.png');cfg['frames'][1]['joints']['b']=[9,22]
 layer=src.copy();ImageDraw.Draw(layer).rectangle((9,16,22,17),fill=(0,0,0,0));layer.save(base/'limb.png')
 for frame in cfg['frames']:
  frame['limb_layers']={'left':'limb.png'};frame['joints']['left_ankle']=[16,16]
 cfg['alpha_threshold']=224;cfg['attachments']=[{'joint':'left_ankle','layer':'left','radius':2,'minimum_opaque_fraction':.95}]
 failure=audit(cfg,base);assert any('limb left' in e for e in failure['errors']) and any('opaque fraction' in e for e in failure['errors'])
 src.save(base/'limb.png');assert audit(cfg,base)['ok']
tests.append('audit rejects detached fragments and annotated bone violations')
tests.append('independent limb/opaque attachment checks detect gaps hidden by the other artwork')
report={'ok':True,'tests':tests};print(json.dumps(report,indent=2))
