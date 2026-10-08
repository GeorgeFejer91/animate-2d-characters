"""Exercise visible-motion diagnostics without treating metrics as art approval."""
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from audit_sequence import audit


def run():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        def sequence(prefix,size,hidden=0):
            files=[]
            for i,x in enumerate((4,5,8,4)):
                pixels=np.zeros((size,size,4),dtype=np.uint8)
                pixels[:,:,:3]=hidden
                pixels[4:8,x:x+4]=[90,110,130,255]
                file=f'{prefix}-{i}.png';Image.fromarray(pixels).save(root/file);files.append(file)
            return {'frames':[{'file':file,'duration_ms':duration} for file,duration in zip(files,(100,200,400,100))], 'cyclic':True}
        small=audit(sequence('small',16),root)
        padded=audit(sequence('padded',64),root)
        hidden=audit(sequence('hidden',16,240),root)
        assert small['ok'] and padded['ok'] and hidden['ok']
        assert small['distinct_visible_frames']==3 and small['repeated_endpoint']
        assert [(s['from'],s['to']) for s in small['steps']]==[(0,1),(1,2),(2,3),(3,0)]
        assert small['steps'][-1]['visible_mean_difference']==0
        for a,b,c in zip(small['steps'],padded['steps'],hidden['steps']):
            assert abs(a['visible_mean_difference']-b['visible_mean_difference'])<1e-7
            assert abs(a['visible_mean_difference']-c['visible_mean_difference'])<1e-7
            assert abs(a['visible_change_per_second']-a['visible_mean_difference']*1000/a['duration_ms'])<1e-7
        assert small['steps'][0]['mean_difference']>padded['steps'][0]['mean_difference']
        assert [f['visible_rgba_sha256'] for f in small['frames']]==[f['visible_rgba_sha256'] for f in hidden['frames']]
        nonloop=sequence('nonloop',16);nonloop['cyclic']=False
        assert len(audit(nonloop,root)['steps'])==3
        nonloop['frames'][0]['duration_ms']=True
        invalid=audit(nonloop,root)
        assert not invalid['ok'] and invalid['steps'][0]['visible_change_per_second'] is None
        still=sequence('still',16)
        still['frames']=[still['frames'][0]]*3
        assert audit(still,root)['distinct_visible_frames']==1
    print('PASS: padding, hidden RGB, exact duplicates, seam, durations and invalid timing')


if __name__=='__main__':run()
