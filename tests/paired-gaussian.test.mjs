import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {sampleArc,sampleOwnedTrajectory,validateGaussianManifest,unpackGaussianRecords,createGaussianActor} from '../assets/paired-gaussian/actor.mjs';
import {createGaussianOwner} from '../assets/paired-gaussian/owner.mjs';
import {anchorBlend,createPaintedAnchor} from '../assets/paired-gaussian/anchor.mjs';

const fixture=new URL('../assets/paired-gaussian/fixture/built/',import.meta.url);
const specUrl=new URL('../assets/paired-gaussian/fixture/spec.json',import.meta.url);
const manifest=JSON.parse(readFileSync(new URL('synthetic-action.json',fixture)));
const sha=buffer=>createHash('sha256').update(buffer).digest('hex');
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);

test('builder output is deterministic from synthetic registered PNGs',()=>{
 const temporary=mkdtempSync(join(tmpdir(),'paired-gaussian-'));
 try{
  const paintings=join(temporary,'paintings');
  const generator=spawnSync('python',['scripts/make_paired_gaussian_fixture.py','--output',paintings],
   {cwd:new URL('..',import.meta.url),encoding:'utf8'});
  assert.equal(generator.status,0,generator.stderr);
  for(const name of ['work','bridge','gesture']){
   assert.equal(sha(readFileSync(join(paintings,`${name}.png`))),
    sha(readFileSync(new URL(`${name}.png`,specUrl))),`${name} PNG generator must match the named held-baton spec`);
  }
  const command=spawnSync('python',['scripts/build_paired_gaussian.py','--spec','assets/paired-gaussian/fixture/spec.json','--output',temporary],{cwd:new URL('..',import.meta.url),encoding:'utf8'});
  assert.equal(command.status,0,command.stderr);
  for(const variant of ['desktop','mobile']){
   const file=manifest.variants[variant].file;
   assert.equal(sha(readFileSync(join(temporary,file))),sha(readFileSync(new URL(file,fixture))));
  }
  for(const frame of Object.values(manifest.anchors.frames))
   assert.equal(sha(readFileSync(join(temporary,frame.file))),sha(readFileSync(new URL(frame.file,fixture))));
  assert.deepEqual(JSON.parse(readFileSync(join(temporary,'synthetic-action.json'))),manifest);
 }finally{rmSync(temporary,{recursive:true,force:true})}
});

test('builder constrains unmatched alpha-zero endpoints to their own painted part',()=>{
 const result=spawnSync('python',['-m','unittest','discover','-s','tests','-p','test_paired_gaussian_builder.py'],
  {cwd:new URL('..',import.meta.url),encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);
 assert.match(result.stderr,/Ran 7 tests/);
});

test('arc sampling keeps keys moving and the reverse/roundtrip seam continuous',()=>{
 const first=sampleArc(manifest,{arc:'extend',phase:0,pose:'work'});
 assert.deepEqual([first.segment,first.u],[0,0]);
 const boundary=sampleArc(manifest,{arc:'extend',phase:.45/1.1,pose:'work'});
 assert.deepEqual([boundary.segment,boundary.u],[1,0]);
 const end=sampleArc(manifest,{arc:'extend',phase:1,pose:'work'});
 assert.deepEqual([end.segment,end.u],[1,1]);
 const back=sampleArc(manifest,{arc:'extend-back',phase:0,pose:'gesture'});
 assert.deepEqual([back.segment,back.u],[1,1]);
 const roundtrip=sampleArc(manifest,{arc:'extend-roundtrip',phase:.5,pose:'gesture'});
 assert.deepEqual([roundtrip.segment,roundtrip.u],[1,1]);
 assert.deepEqual([sampleArc(manifest,{arc:'extend-roundtrip',phase:1}).segment,sampleArc(manifest,{arc:'extend-roundtrip',phase:1}).u],[0,0]);
 assert.equal(sampleArc(manifest,{arc:null,pose:'work'}).u,0);
 assert.equal(sampleArc(manifest,{arc:null,pose:'gesture'}).u,1);
});

test('binary decoder bounds records and adjacent arcs share exact visible bridge paint',()=>{
 const variant='desktop',spec=validateGaussianManifest(manifest,variant);
 const gzip=readFileSync(new URL(spec.file,fixture)),raw=gunzipSync(gzip);
 assert.equal(sha(gzip),spec.sha256);assert.equal(sha(raw),spec.decoded_sha256);
 const records=unpackGaussianRecords(manifest,variant,raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength));
 assert.equal(records.count,256);assert.equal(records.segments,3);
 const cloud=(segment,endpoint)=>{
  const values=[];
  for(let slot=0;slot<records.count;slot++){
   const base=(segment*records.count+slot)*4,paint=endpoint?records.end:records.start;
   if(!paint[base+3])continue;
   const x=records.xy[base+(endpoint?2:0)],y=records.xy[base+(endpoint?3:1)];
   values.push(`${x.toFixed(7)}:${y.toFixed(7)}:${[...paint.slice(base,base+4)].join(',')}`);
  }
  return values.sort();
 };
 assert.deepEqual(cloud(0,1),cloud(1,0),'one bridge painting is shared across segment boundary');
 assert.throws(()=>unpackGaussianRecords(manifest,variant,new ArrayBuffer(raw.length-24)),/record length/);
 const invalid=structuredClone(manifest);invalid.variants.desktop.sample_count=20224;
 assert.throws(()=>validateGaussianManifest(invalid),/Invalid Gaussian/);
});

test('fixture held baton rotates through its direct arc without a collapsed midpoint',()=>{
 const swing=sampleArc(manifest,{arc:'swing',phase:.5,pose:'work'});
 assert.deepEqual([swing.segment,swing.u],[2,.5]);
 for(const variant of ['desktop','mobile']){
  const selected=validateGaussianManifest(manifest,variant);
  assert.equal(selected.trajectories.length,3);
  const raw=gunzipSync(readFileSync(new URL(selected.file,fixture)));
  const records=unpackGaussianRecords(manifest,variant,raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.length));
  const curve=selected.trajectories.find(item=>item.segment===swing.segment);
  assert(curve&&curve.start_slot<curve.end_slot);
  let tip=null;
  for(let slot=curve.start_slot;slot<curve.end_slot;slot++){
   const index=(swing.segment*records.count+slot)*4;
   if(!records.start[index+3]||!records.end[index+3])continue;
   const start=[records.xy[index],records.xy[index+1]],end=[records.xy[index+2],records.xy[index+3]];
   const radius=Math.hypot(start[0]-curve.pivot_start[0],start[1]-curve.pivot_start[1]);
   if(!tip||radius>tip.radius)tip={start,end,radius};
  }
  assert(tip,`${variant} needs visible paired prop paint`);
  const curved=sampleOwnedTrajectory(curve,tip.start,tip.end,.5);
  const linear=tip.start.map((value,i)=>(value+tip.end[i])/2);
  const radius=point=>Math.hypot(point[0]-curve.pivot_start[0],point[1]-curve.pivot_start[1]);
  assert(radius(curved)>radius(linear)*1.05,`${variant} rotating held object loses less extent than straight interpolation`);
  sampleOwnedTrajectory(curve,tip.start,tip.end,0).forEach((value,i)=>near(value,tip.start[i]));
  sampleOwnedTrajectory(curve,tip.start,tip.end,1).forEach((value,i)=>near(value,tip.end[i]));
 }
});

test('trajectory bounds, disjoint ranges and a translated half-turn are explicit',()=>{
 const curve={segment:0,start_slot:12,end_slot:32,pivot_start:[0,0],pivot_end:[.2,0],angle_radians:Math.PI};
 const start=[1,0],end=[-.8,0];
 sampleOwnedTrajectory(curve,start,end,0).forEach((value,i)=>near(value,start[i]));
 sampleOwnedTrajectory(curve,start,end,1).forEach((value,i)=>near(value,end[i]));
 const midpoint=sampleOwnedTrajectory(curve,start,end,.5);
 near(midpoint[0],.1);near(midpoint[1],1);
 const valid=structuredClone(manifest);valid.variants.desktop.trajectories=[curve,{...curve,start_slot:32,end_slot:48}];
 assert.equal(validateGaussianManifest(valid).trajectories.length,2,'two disjoint regions can share a segment');
 for(const bad of [
  {...curve,segment:manifest.segments.length},
  {...curve,start_slot:32},
  {...curve,end_slot:manifest.variants.desktop.sample_count+1},
  {...curve,pivot_start:[4.01,0]},
  {...curve,pivot_end:[0,Infinity]},
  {...curve,angle_radians:Math.PI+.001},
 ]){
  const invalid=structuredClone(valid);invalid.variants.desktop.trajectories=[bad];
  assert.throws(()=>validateGaussianManifest(invalid),/trajectory/);
 }
 const overlapping=structuredClone(valid);
 overlapping.variants.desktop.trajectories=[curve,{...curve,start_slot:31,end_slot:48}];
 assert.throws(()=>validateGaussianManifest(overlapping),/Overlapping/);
 const tooMany=structuredClone(valid);
 tooMany.variants.desktop.trajectories=Array.from({length:9},(_,i)=>({...curve,start_slot:i*2,end_slot:i*2+1}));
 assert.throws(()=>validateGaussianManifest(tooMany),/excessive/);
});

test('builder emits multiple disjoint regions and keeps old specs linear',()=>{
 const temporary=mkdtempSync(join(tmpdir(),'paired-gaussian-regions-'));
 const original=JSON.parse(readFileSync(specUrl));
 for(const state of original.states)state.file=fileURLToPath(new URL(state.file,specUrl));
 const run=(name,spec)=>{
  const source=join(temporary,`${name}.json`),destination=join(temporary,name);
  writeFileSync(source,JSON.stringify(spec));
  const result=spawnSync('python',['scripts/build_paired_gaussian.py','--spec',source,'--output',destination],
    {cwd:new URL('..',import.meta.url),encoding:'utf8'});
  return{result,manifest:result.status===0?JSON.parse(readFileSync(join(destination,'synthetic-action.json'))):null};
 };
 try{
  const legacy=structuredClone(original);
  for(const state of legacy.states)for(const region of state.regions){delete region.pivot_xy;delete region.orientation_landmarks}
  const old=run('legacy',legacy);assert.equal(old.result.status,0,old.result.stderr);
  assert(old.manifest.variants.desktop.trajectories===undefined,'legacy region specs stay linear');
  assert.equal(validateGaussianManifest(old.manifest).record_bytes,24);
  const multi=structuredClone(original);
  for(const state of multi.states)state.regions.push({part:'test_patch',polygon:[[24,51],[32,51],[32,61],[24,61]],
    pivot_xy:[27,55],orientation_landmarks:['base','core']});
  const built=run('multi',multi);assert.equal(built.result.status,0,built.result.stderr);
  for(const variant of ['desktop','mobile']){
   const entries=built.manifest.variants[variant].trajectories;
   assert.equal(entries.length,6,'two owned regions across three segments');
   for(let segment=0;segment<3;segment++){
    const [a,b]=entries.filter(item=>item.segment===segment).sort((x,y)=>x.start_slot-y.start_slot);
    assert(a.end_slot<=b.start_slot,'builder assigns disjoint slot ranges');
   }
   validateGaussianManifest(built.manifest,variant);
  }
  const overlap=structuredClone(original);
  for(const state of overlap.states)state.regions.push({part:'duplicate',polygon:state.regions[0].polygon,
    pivot_xy:[39,29],orientation_landmarks:['grip','tip']});
  const rejected=run('overlap',overlap);
  assert.notEqual(rejected.result.status,0);
  assert.match(rejected.result.stderr,/Overlapping curved regions/);
 }finally{rmSync(temporary,{recursive:true,force:true})}
});

test('shared owner defers retirement through one pending sort and reports failure',async()=>{
 let now=0,resolve,reject,sorts=0,disposed=0;
 const members=new Set(),scene={add:x=>members.add(x),remove:x=>members.delete(x)};
 class SparkRenderer{constructor(options){this.options=options;this.activeSplats=7;this.visible=false}setDirty(){}update(){sorts++;return new Promise((yes,no)=>{resolve=yes;reject=no})}dispose(){disposed++}}
 class SplatMesh{constructor(){this.visible=true;this.disposals=0}dispose(){this.disposals++}}
 const owner=await createGaussianOwner({renderer:{},scene,sparkModule:{SparkRenderer,SplatMesh,dyno:{}},nowMs:()=>now});
 const mesh=owner.attach(new SplatMesh());const work=owner.update({});await Promise.resolve();
 now=20;assert.equal(owner.update({}),work);assert.equal(sorts,1);
 let textures=0;owner.retire(mesh,()=>textures++);
 assert.equal(members.has(mesh),false);assert.equal(mesh.disposals,0);
 resolve();await work;assert.equal(mesh.disposals,1);assert.equal(textures,1);
 const second=owner.attach(new SplatMesh());const failed=owner.update({});await Promise.resolve();reject(new Error('sort failed'));await failed;
 assert.equal(owner.inspect().failure,'sort failed');assert.equal(second.visible,false);
 await owner.dispose();assert.equal(disposed,1);assert.equal(second.disposals,1);
});

test('shared owner caps sort cadence and disposes after an in-flight update',async()=>{
 let now=0,finish,updates=0,disposed=0;
 class SparkRenderer{constructor(){this.activeSplats=1}setDirty(){}update(){updates++;return new Promise(resolve=>{finish=resolve})}dispose(){disposed++}}
 const scene={add(){},remove(){}},mesh={visible:true,dispose(){this.disposals=(this.disposals||0)+1}};
 const owner=await createGaussianOwner({renderer:{},scene,sparkModule:{SparkRenderer,SplatMesh:class{},dyno:{}},nowMs:()=>now});
 owner.attach(mesh);
 let first=owner.update({});await Promise.resolve();finish();await first;
 now=10;assert.equal(owner.update({},120),null,'requested rate cannot exceed 60 Hz');
 now=17;let second=owner.update({});await Promise.resolve();assert.equal(updates,2);
 const teardown=owner.dispose();assert.equal(mesh.visible,false);assert.equal(mesh.disposals||0,0);
 finish();await second;await teardown;await owner.dispose();
 assert.equal(mesh.disposals,1);assert.equal(disposed,1);
});

test('actor decodes native gzip and keeps host pivot, one cloud and sort readiness',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=async url=>{const bytes=readFileSync(new URL(url));return{ok:true,json:async()=>JSON.parse(bytes.toString()),arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}};
 const textures=[];
 class DataTexture{constructor(data,w,h){this.data=data;this.width=w;this.height=h;this.disposals=0;textures.push(this)}dispose(){this.disposals++}}
 class Vector2{set(x,y){this.x=x;this.y=y}}
 class Vector3{constructor(x=0,y=0,z=0){this.x=x;this.y=y;this.z=z}set(x,y,z){this.x=x;this.y=y;this.z=z;return this}copy(other){Object.assign(this,other);return this}}
 class SplatMesh{constructor(options){this.options=options;this.initialized=Promise.resolve();this.position=new Vector3();this.quaternion={copy(){}};this.scale={setScalar:x=>{this.size=x}}}updateGenerator(){}}
 let shader='',uniformInputs;
 class Dyno{constructor(options){this.options=options}apply(inputs){uniformInputs=inputs;const names=Object.fromEntries(Object.keys(inputs).map(key=>[key,key]));shader=this.options.statements({inputs:names,outputs:{gsplat:'outGsplat'}});return{gsplat:'compiled'}}}
 const dyno={Gsplat:'Gsplat',Dyno,unindentLines:value=>value,dynoSampler2D:value=>value,
  dynoFloat:value=>({value}),dynoVec2:value=>({value}),dynoVec3:value=>({value}),dynoBlock:(_in,_out,build)=>build({gsplat:'inGsplat'})};
 const owner={SplatMesh,dyno,started:0,completed:0,attach(mesh){this.mesh=mesh},retire(mesh,cleanup){this.retired=mesh;cleanup()},inspect(){return{ready:true,startedUpdates:this.started,completedUpdates:this.completed,activeSplats:5,pending:false,failure:''}}};
 const THREE={DataTexture,Vector2,Vector3,Quaternion:class{},Color:class{},FloatType:'float',UnsignedByteType:'byte',RGBAFormat:'rgba',NearestFilter:'nearest',ClampToEdgeWrapping:'clamp'};
 try{
  const actor=await createGaussianActor({THREE,owner,manifestUrl:new URL('synthetic-action.json',fixture),anchorPaint:false});
  assert.equal(owner.mesh.options.maxSplats,256);assert.equal(textures.length,3);
  assert.match(shader,/int slot=cell\.x\+cell\.y\*256;/);
  assert.match(shader,/if\(int\(segment\)==2&&slot>=205&&slot<251\)/);
  assert.match(shader,/p=mix\(pivotA,pivotB,u\)\+vec2\(cos\(theta\)/);
  assert.match(shader,/float local=mix\(1\.,moving\*\(1\.-faceEnabled\*faceMask\)\*planted,painted\)/);
  assert(!shader.includes('${'),'generated Spark code must not contain unresolved placeholders');
  const host={geometry:{parameters:{height:2}},scale:{y:1},position:new Vector3(2,1,-3),rotation:{x:0,y:.2,z:0},quaternion:{}};
  assert.equal(actor.update({arc:'extend',phase:.2,pose:'work',speaking:true,mouthFrame:2},host),false);
  assert.equal(uniformInputs.painted.value,0);assert.equal(uniformInputs.strength.value,1,'cloud-only manifests keep full Gaussian paint');
  near(owner.mesh.position.y,0);near(owner.mesh.size,2);
  owner.started=owner.completed=1;
  assert.equal(actor.update({arc:'extend',phase:.2,pose:'work'},host),true);
  assert.equal(actor.inspect().trajectoryCount,3);
  assert.equal(actor.inspect().activeTrajectories.length,1);
  actor.dispose();assert.equal(owner.retired,owner.mesh);assert(textures.every(texture=>texture.disposals===1));
 }finally{globalThis.fetch=original}
});
