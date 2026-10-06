"""Portable behavioural fixtures for the final-frame provenance/completeness gate.

Synthetic images are test fixtures only; their all-pass reviews are not claims
about production artwork. Run with --output-dir to retain every fixture/report.
"""
import argparse,copy,hashlib,json,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw

CATEGORIES=('identity','proportions','rendering_style','lighting_color','contour','texture','anatomy_occlusion','motion')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf-8')
def pose(offset):
    im=Image.new('RGBA',(16,16));d=ImageDraw.Draw(im)
    d.rectangle((5,2,10,4),fill=(210,150,100,255))
    d.rectangle((4,5,11,9),fill=(50,100,180,255))
    d.rectangle((3,6,5,8),fill=(180,30,30,255))
    for x in [5,9]:
        d.rectangle((x+offset,9,x+offset+1,11),fill=(210,150,100,255))
        d.rectangle((x+offset,12,x+offset+1,13),fill='white')
        d.rectangle((x+offset,14,x+offset+2,14),fill=(80,50,25,255))
    return im
def fixture(folder):
    folder.mkdir(parents=True,exist_ok=True);images=[pose(0),pose(1)]
    atlas=Image.new('RGBA',(32,16));atlas.alpha_composite(images[0]);atlas.alpha_composite(images[1],(16,0));atlas.save(folder/'export.png')
    images[0].save(folder/'canonical.png');atlas.save(folder/'ordered.png')
    frames=[];reviews=[]
    for i,im in enumerate(images):
        name=f'frame-{i}.png';im.save(folder/name)
        comparison=Image.new('RGBA',(32,16),(220,220,220,255));comparison.alpha_composite(images[0]);comparison.alpha_composite(im,(16,0));comparison.save(folder/f'compare-{i}.png')
        evidence=[{'role':'source_comparison','file':f'compare-{i}.png','sha256':sha(folder/f'compare-{i}.png'),'reference_ids':['canonical']}, {'role':'native','file':name,'sha256':sha(folder/name)}, {'role':'ordered_motion','file':'ordered.png','sha256':sha(folder/'ordered.png')}]
        for role,bg in [('enlarged_light',(240,240,240,255)),('enlarged_dark',(30,30,30,255))]:
            proof=Image.new('RGBA',im.size,bg);proof.alpha_composite(im);proof=proof.resize((32,32),Image.Resampling.NEAREST)
            file=f'{role}-{i}.png';proof.save(folder/file);evidence.append({'role':role,'file':file,'sha256':sha(folder/file)})
        frames.append({'id':f'f{i}','file':name,'sha256':sha(folder/name),'row':0,'col':i,'reference_ids':['canonical']})
        reviews.append({'id':f'f{i}','sha256':sha(folder/name),'reference_ids':['canonical'],'verdict':'pass','unresolved_findings':[], 'analysis':{cat:{'status':'pass','observation':f'Synthetic {cat}: connected test sprite pixels compared with canonical fixture.'} for cat in CATEGORIES},'evidence':evidence})
    manifest={'export':{'file':'export.png','sha256':sha(folder/'export.png')},'cell_size_xy':[16,16],'movement_rows':[{'row':0,'count':2}],'references':[{'id':'canonical','file':'canonical.png','sha256':sha(folder/'canonical.png')}],'frames':frames}
    review={'reviewer':'Synthetic behavioural fixture','export_sha256':sha(folder/'export.png'),'reference_sha256':{'canonical':sha(folder/'canonical.png')},'ordered_motion_reviewed':True,'frames':reviews}
    return manifest,review
def edit_pixel(file):
    im=Image.open(file).convert('RGBA');im.putpixel((0,0),(50,30,90,255));im.save(file)
def canonical_changed_after_review(m,r,f):
    edit_pixel(f/'canonical.png');m['references'][0]['sha256']=sha(f/'canonical.png')
def invalid_media(m,r,f):
    p=f/'not-image.txt';p.write_text('not image evidence');r['frames'][0]['evidence'][0].update({'file':p.name,'sha256':sha(p)})
def mismatched_frame(m,r,f):
    edit_pixel(f/'frame-0.png');h=sha(f/'frame-0.png');m['frames'][0]['sha256']=h;r['frames'][0]['sha256']=h
    for proof in r['frames'][0]['evidence']:
        if proof['file']=='frame-0.png':proof['sha256']=h
def partial_row(m,r,f):
    # Cropping to a half-height cell should not produce a valid complete row.
    im=Image.open(f/'export.png').convert('RGBA');im.crop((0,0,32,15)).save(f/'export.png')
    m['export']['sha256']=sha(f/'export.png');r['export_sha256']=m['export']['sha256']
    im=Image.open(f/'export.png').convert('RGBA')
    for i in range(2):
        p=f/f'frame-{i}.png';im.crop((i*16,0,(i+1)*16,16)).save(p);h=sha(p);m['frames'][i]['sha256']=h;r['frames'][i]['sha256']=h
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();root=a.output_dir.resolve();root.mkdir(parents=True,exist_ok=True)
    helper=Path(__file__).with_name('audit_final_frame_analysis.py');checks=[]
    cases=[
      ('valid',True,None),
      ('export-stale',False,lambda m,r,f:edit_pixel(f/'export.png')),
      ('frame-stale',False,lambda m,r,f:edit_pixel(f/'frame-0.png')),
      ('frame-final-pixel-mismatch',False,mismatched_frame),
      ('canonical-stale',False,lambda m,r,f:edit_pixel(f/'canonical.png')),
      ('canonical-changed-after-review',False,canonical_changed_after_review),
      ('missing-category',False,lambda m,r,f:r['frames'][0]['analysis'].pop('texture')),
      ('qualified-verdict',False,lambda m,r,f:r['frames'][0].update({'verdict':'pass with qualification'})),
      ('unresolved-findings',False,lambda m,r,f:r['frames'][0].update({'unresolved_findings':['unresolved knee tear']})),
      ('incomplete-row-coverage',False,lambda m,r,f:m['frames'].pop()),
      ('incomplete-visual-review',False,lambda m,r,f:r['frames'].pop()),
      ('invalid-media',False,invalid_media),
      ('nan-row',False,lambda m,r,f:m['movement_rows'][0].update({'row':float('nan')})),
      ('infinite-cell',False,lambda m,r,f:m.update({'cell_size_xy':[float('inf'),16]})),
      ('negative-column',False,lambda m,r,f:m['frames'][0].update({'col':-1})),
      ('boolean-cell',False,lambda m,r,f:m.update({'cell_size_xy':[True,16]})),
      ('fractional-row',False,lambda m,r,f:m['movement_rows'][0].update({'row':.5})),
      ('string-loop-reviewed',False,lambda m,r,f:r.update({'ordered_motion_reviewed':'true'})),
      ('missing-frame-key',False,lambda m,r,f:m['frames'][0].pop('reference_ids')),
      ('partial-export-cell',False,partial_row),
      ('empty-required-reference-ids',False,lambda m,r,f:m['frames'][0].update({'reference_ids':[]})),
      ('empty-frame-id',False,lambda m,r,f:(m['frames'][0].update({'id':''}),r['frames'][0].update({'id':''}))),
    ]
    def run(name,accept,mut=None,report_target=None):
        f=root/name;m,r=fixture(f)
        if mut:mut(m,r,f)
        write(f/'manifest.json',m);write(f/'review.json',r)
        report=f/(report_target or 'report.json');before={x.name:sha(x) for x in f.iterdir() if x.is_file()}
        cmd=[sys.executable,str(helper),str(f/'manifest.json'),'--review',str(f/'review.json'),'--report',str(report)]
        proc=subprocess.run(cmd,capture_output=True,text=True)
        try:result=json.loads(proc.stdout.strip().splitlines()[-1]);structured=isinstance(result,dict) and isinstance(result.get('ok'),bool)
        except (ValueError,IndexError):result={};structured=False
        accepted=proc.returncode==0 and result.get('ok') is True
        stable=all((f/file).is_file() and sha(f/file)==digest for file,digest in before.items()) if report_target else True
        checks.append({'case':name,'expected_accept':accept,'accepted':accepted,'structured_result':structured,'passed':structured and accepted==accept and stable,'exit_code':proc.returncode,'inputs_unchanged':stable,'errors':result.get('errors',[]),'stderr':proc.stderr[-700:]})
    for name,accept,mut in cases:run(name,accept,mut)
    for target in ['manifest.json','review.json','export.png','canonical.png','frame-0.png','compare-0.png','ordered.png','enlarged_light-0.png']:
        run('overwrite-'+target.replace('.','-'),False,report_target=target)
    summary={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks}
    write(root/'test-report.json',summary);print(json.dumps(summary,indent=2));return 0 if all(c['passed'] for c in checks) else 1
if __name__=='__main__':raise SystemExit(main())
