import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {sampleArc,validateGaussianManifest,unpackGaussianRecords,createGaussianActor} from '../assets/paired-gaussian/actor.mjs';
import {createGaussianOwner} from '../assets/paired-gaussian/owner.mjs';

const fixture=new URL('../assets/paired-gaussian/fixture/built/',import.meta.url);
const manifest=JSON.parse(readFileSync(new URL('synthetic-action.json',fixture)));
const sha=buffer=>createHash('sha256').update(buffer).digest('hex');
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);

test('builder output is deterministic from synthetic registered PNGs',()=>{
 const temporary=mkdtempSync(join(tmpdir(),'paired-gaussian-'));
 try{
  const command=spawnSync('python',['scripts/build_paired_gaussian.py','--spec','assets/paired-gaussian/fixture/spec.json','--output',temporary],{cwd:new URL('..',import.meta.url),encoding:'utf8'});
  assert.equal(command.status,0,command.stderr);
  for(const variant of ['desktop','mobile']){
   const file=manifest.variants[variant].file;
   assert.equal(sha(readFileSync(join(temporary,file))),sha(readFileSync(new URL(file,fixture))));
  }
 }finally{rmSync(temporary,{recursive:true,force:true})}
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
 assert.equal(records.count,256);assert.equal(records.segments,2);
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
 const owner={SplatMesh,dyno:{Gsplat:'Gsplat',dynoFloat:value=>({value}),dynoVec2:value=>({value}),dynoBlock:()=>({})},started:0,completed:0,attach(mesh){this.mesh=mesh},retire(mesh,cleanup){this.retired=mesh;cleanup()},inspect(){return{ready:true,startedUpdates:this.started,completedUpdates:this.completed,activeSplats:5,pending:false,failure:''}}};
 const THREE={DataTexture,Vector2,Vector3,Quaternion:class{},Color:class{},FloatType:'float',UnsignedByteType:'byte',RGBAFormat:'rgba',NearestFilter:'nearest',ClampToEdgeWrapping:'clamp'};
 try{
  const actor=await createGaussianActor({THREE,owner,manifestUrl:new URL('synthetic-action.json',fixture)});
  assert.equal(owner.mesh.options.maxSplats,256);assert.equal(textures.length,3);
  const host={geometry:{parameters:{height:2}},scale:{y:1},position:new Vector3(2,1,-3),rotation:{x:0,y:.2,z:0},quaternion:{}};
  assert.equal(actor.update({arc:'extend',phase:.2,pose:'work',speaking:true,mouthFrame:2},host),false);
  near(owner.mesh.position.y,0);near(owner.mesh.size,2);
  owner.started=owner.completed=1;
  assert.equal(actor.update({arc:'extend',phase:.2,pose:'work'},host),true);
  actor.dispose();assert.equal(owner.retired,owner.mesh);assert(textures.every(texture=>texture.disposals===1));
 }finally{globalThis.fetch=original}
});
