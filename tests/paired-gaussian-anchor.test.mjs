import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createPaintedAnchor,anchorBlend} from '../assets/paired-gaussian/anchor.mjs';
import {createGaussianOwner} from '../assets/paired-gaussian/owner.mjs';
import {sampleArc} from '../assets/paired-gaussian/actor.mjs';

const fixture=new URL('../assets/paired-gaussian/fixture/built/',import.meta.url);
const manifest=JSON.parse(readFileSync(new URL('synthetic-action.json',fixture)));
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);

test('registered keys retain full paint and a brief midpoint handoff covers the texture swap',()=>{
 const work=anchorBlend(manifest,sampleArc(manifest,{arc:null,pose:'work'}));
 assert.deepEqual(work,{state:'work',opacity:1});
 const first=anchorBlend(manifest,sampleArc(manifest,{arc:'extend',phase:0}));
 const bridge=anchorBlend(manifest,sampleArc(manifest,{arc:'extend',phase:.45/1.1}));
 const terminal=anchorBlend(manifest,sampleArc(manifest,{arc:'extend',phase:1}));
 assert.deepEqual([first.state,first.opacity,bridge.state,bridge.opacity,terminal.state,terminal.opacity],
  ['work',1,'bridge',1,'gesture',1]);
 const middle=anchorBlend(manifest,sampleArc(manifest,{arc:'extend',phase:.225/1.1}));
 assert.equal(middle.opacity,0);
 const nearKey=anchorBlend(manifest,{segment:0,u:.1,arc:'extend'});
 assert.equal(nearKey.opacity,1,'ordinary motion remains sharp painted art');
 const nearMidpoint=anchorBlend(manifest,{segment:0,u:.4,arc:'extend'});
 assert(nearMidpoint.opacity>0&&nearMidpoint.opacity<1);
 near(anchorBlend(manifest,{segment:0,u:.6,arc:'extend'}).opacity,nearMidpoint.opacity);
 assert.equal(anchorBlend(manifest,sampleArc(manifest,{arc:'extend-back',phase:0})).state,'gesture');
});

function fakeThree(){
 const disposed={bitmaps:0,textures:0,planes:0,materials:0};
 class Vector2{set(x,y){this.x=x;this.y=y}}
 class Vector3{constructor(x=0,y=0,z=0){this.x=x;this.y=y;this.z=z}copy(value){Object.assign(this,value);return this}}
 class PlaneGeometry{constructor(width,height,widthSegments,heightSegments){this.parameters={width,height,widthSegments,heightSegments}}dispose(){disposed.planes++}}
 class MeshBasicMaterial{constructor(options){Object.assign(this,options);this.color={copy(value){this.value=value}};this.userData={}}dispose(){disposed.materials++}}
 class Texture{constructor(bitmap){this.image=bitmap}dispose(){disposed.textures++}}
 class Mesh{constructor(geometry,material){this.geometry=geometry;this.material=material;this.position=new Vector3();this.quaternion={copy(value){this.value=value}};this.scale={setScalar(value){this.value=value}};this.userData={}}}
 return{THREE:{PlaneGeometry,MeshBasicMaterial,Texture,Mesh,DoubleSide:2,SRGBColorSpace:'srgb',LinearFilter:1,Vector2,Vector3,Color:class{},ShaderChunk:{map_fragment:'diffuseColor *= texture2D(map, vMapUv);'}},disposed};
}

test('anchor cache stays at three painted frames and keeps source floor/aspect',async()=>{
 const priorFetch=globalThis.fetch,priorBitmap=globalThis.createImageBitmap;
 const {THREE,disposed}=fakeThree(),painted=new Set(),requested=[];
 let liveBitmaps=0,peakBitmaps=0;
 globalThis.fetch=async url=>{requested.push(String(url));const bytes=readFileSync(new URL(url));return{ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}};
 globalThis.createImageBitmap=async()=>{liveBitmaps++;peakBitmaps=Math.max(peakBitmaps,liveBitmaps);
  return{width:64,height:64,close(){disposed.bitmaps++;liveBitmaps--}}};
 const owner={attachPaint(mesh){painted.add(mesh)},retirePaint(mesh){painted.delete(mesh)}};
 const extended=structuredClone(manifest);
 extended.states.push({id:'extra',landmarks:structuredClone(manifest.states[0].landmarks)});
 extended.segments.push({from:'gesture',to:'extra'});
 extended.anchors.frames.extra={...extended.anchors.frames.work};
 const source={geometry:{parameters:{height:2}},scale:{y:1.2},position:new THREE.Vector3(3,1.2,-4),quaternion:{},material:{color:{r:.7},userData:{breath:{value:.3}}}};
 try{
  const paint=await createPaintedAnchor({THREE,owner,manifest:extended,manifestUrl:new URL('synthetic-action.json',fixture)});
  assert.equal(painted.size,1);assert.equal(paint.inspect().resident,1);
  assert.equal(paint.update({segment:0,u:0,arc:null},source,true,{speaking:true,mouthFrame:2}),1);
  const plane=[...painted][0];near(plane.geometry.parameters.width,1);near(plane.scale.value,2.4);
  assert.deepEqual([plane.geometry.parameters.widthSegments,plane.geometry.parameters.heightSegments],[32,32]);
  near(plane.position.y,source.position.y);
  const shader={uniforms:{},fragmentShader:'#include <map_fragment>',vertexShader:'#include <begin_vertex>'};plane.material.onBeforeCompile(shader);
  assert.match(shader.fragmentShader,/texture2D\(map, paintUv\)/);
  assert.match(shader.vertexShader,/anchorControlSource\[32\]/);
  assert.match(shader.vertexShader,/transformed\.xy=p-vec2\(0\.,\.5\)/);
  assert.equal(shader.uniforms.anchorControlCount.value,5);
  near(shader.uniforms.anchorMouth.value,.9);
  near(shader.uniforms.anchorMouthCenter.value.x,.5);
  near(shader.uniforms.anchorMouthCenter.value.y,1-17/64);
  const tip=2,sourceTip=shader.uniforms.anchorControlSource.value[tip],targetTip=shader.uniforms.anchorControlTarget.value[tip];
  near(sourceTip.x,(51-32)/64);near(targetTip.x,sourceTip.x);
  paint.update({segment:0,u:.25,arc:'extend'},source,true);
  near(sourceTip.x,(51-32)/64);near(targetTip.x,(50.75-32)/64);
  near(targetTip.y,(64-30.5)/64);
  paint.update({segment:0,u:1,arc:'extend'},source,true);
  near(sourceTip.x,(50-32)/64);near(targetTip.x,sourceTip.x);
  near(sourceTip.y,(64-20)/64);near(targetTip.y,sourceTip.y);
  paint.update({segment:0,u:0,arc:null},source,true,{speaking:true,mouthFrame:2,reducedMotion:true});
  near(shader.uniforms.anchorMouth.value,0);
  for(const sample of [{segment:0,u:1,arc:null},{segment:1,u:1,arc:null},{segment:3,u:1,arc:null}]){
   paint.update(sample,source,true);await paint.settle();paint.update(sample,source,true);
   assert(paint.inspect().resident<=3);
  }
  assert.equal(paint.inspect().state,'extra');assert.equal(paint.inspect().resident,3);
  assert(disposed.bitmaps>=1,'least-needed painting is evicted');
  assert.equal(peakBitmaps,3,'the fourth bitmap is decoded only after eviction');
  assert(requested.every(url=>url.endsWith('.webp')));
  paint.dispose();assert.equal(painted.size,0);assert.equal(disposed.planes,1);assert.equal(disposed.materials,1);
  assert.equal(disposed.textures,disposed.bitmaps);
  assert.equal(liveBitmaps,0);
 }finally{globalThis.fetch=priorFetch;globalThis.createImageBitmap=priorBitmap}
});

test('late decoded paint is closed after abort and cannot reattach',async()=>{
 const priorFetch=globalThis.fetch,priorBitmap=globalThis.createImageBitmap;
 const {THREE,disposed}=fakeThree(),painted=new Set();let release,late=false;
 globalThis.fetch=async url=>{
  if(String(url).endsWith('synthetic-action-anchor-1.webp')){
   late=true;await new Promise(resolve=>{release=resolve});
  }
  const bytes=readFileSync(new URL(url));return{ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};
 };
 globalThis.createImageBitmap=async()=>({width:64,height:64,close(){disposed.bitmaps++}});
 const owner={attachPaint(mesh){painted.add(mesh)},retirePaint(mesh){painted.delete(mesh)}};
 try{
  const paint=await createPaintedAnchor({THREE,owner,manifest,manifestUrl:new URL('synthetic-action.json',fixture)});
  const source={geometry:{parameters:{height:1}},scale:{y:1},position:new THREE.Vector3(),quaternion:{},material:{color:{},userData:{}}};
  paint.update({segment:0,u:1,arc:null},source,true);
  for(let n=0;n<5&&!late;n++)await Promise.resolve();
  assert(late);const settling=paint.settle();paint.dispose();release();await settling;
  assert.equal(painted.size,0);assert.equal(paint.inspect().resident,0);
  assert.equal(disposed.bitmaps,2,'initial and late decoded bitmaps both close');
  assert.equal(disposed.textures,1,'late bitmap never acquires a GPU texture');
 }finally{globalThis.fetch=priorFetch;globalThis.createImageBitmap=priorBitmap}
});

test('anchor creation rejects an already aborted signal before loading',async()=>{
 const request=new AbortController();request.abort();
 let attached=false;
 await assert.rejects(createPaintedAnchor({THREE:{},owner:{attachPaint(){attached=true}},manifest,
  manifestUrl:new URL('synthetic-action.json',fixture),signal:request.signal}),/AbortError/);
 assert.equal(attached,false);
});

test('landmark controls validate before paint geometry or image allocation',async()=>{
 const {THREE}=fakeThree();let attached=false;
 const owner={attachPaint(){attached=true},retirePaint(){}};
 const invalid=[];
 const few=structuredClone(manifest);for(const state of few.states)state.landmarks={only:[0,0]};invalid.push(few);
 const many=structuredClone(manifest);for(const state of many.states)state.landmarks=Object.fromEntries(Array.from({length:33},(_,index)=>['p'+index,[index,1]]));invalid.push(many);
 const nonfinite=structuredClone(manifest);nonfinite.states[0].landmarks.face=[Infinity,0];invalid.push(nonfinite);
 for(const candidate of invalid){
  await assert.rejects(createPaintedAnchor({THREE,owner,manifest:candidate,manifestUrl:new URL('synthetic-action.json',fixture)}),/landmark/);
  assert.equal(attached,false);
 }
});

test('shared owner matches Three clip-Z sorting in perspective and orthographic cameras',async()=>{
 let comparator=null;
 const renderer={setTransparentSort(value){comparator=value}},scene={add(){},remove(){}};
 class SparkRenderer{constructor(){this.activeSplats=1}dispose(){}}
 const owner=await createGaussianOwner({renderer,scene,sparkModule:{SparkRenderer,SplatMesh:class{},dyno:{}}});
 const makePaint=point=>({visible:true,userData:{anchorActive:true},updateMatrixWorld(){},getWorldPosition(){return{applyMatrix4(){return point}}}});
 const farPoint={x:.3,y:-.2,z:-3.85},nearPoint={x:-.4,y:.1,z:-.98};
 const far=makePaint(farPoint),near=makePaint(nearPoint),camera={position:{clone(){return{}}},matrixWorldInverse:{},projectionMatrix:{elements:[]},updateMatrixWorld(){}};
 owner.attachPaint(far);owner.attachPaint(near);assert.equal(typeof comparator,'function');
 const item=(object,z,id)=>({object,z,id,groupOrder:0,renderOrder:0});
 for(const [kind,projection] of [
  ['perspective',{x:.15,y:-.04,z:-1.002,offset:-.2}],
  ['orthographic',{x:0,y:0,z:-.4,offset:-1}],
 ]){
  const e=Array(16).fill(0);e[2]=projection.x;e[6]=projection.y;e[10]=projection.z;e[14]=projection.offset;
  camera.projectionMatrix.elements=e;owner.update(camera);
  const clip=point=>e[2]*point.x+e[6]*point.y+e[10]*point.z+e[14];
  const farZ=clip(farPoint),nearZ=clip(nearPoint),middle=(farZ+nearZ)/2;
  const farItem=item(far,farZ,1),sparkItem=item(owner.spark,-2.08,2),nearItem=item(near,nearZ,3);
  assert(comparator(farItem,sparkItem)<0,`${kind}: far paint renders before Spark batch`);
  assert(comparator(sparkItem,nearItem)<0,`${kind}: Spark batch renders before near paint`);
  assert(comparator(item({},middle+1e-5,4),sparkItem)<0,`${kind}: Spark uses exact clip Z, not camera depth`);
  assert(comparator(sparkItem,item({},middle-1e-5,5))<0,`${kind}: Spark uses exact clip Z, not NDC`);
 }
 owner.retirePaint(far);assert.equal(typeof comparator,'function');
 owner.retirePaint(near);assert.equal(comparator,null);
 await owner.dispose();assert.equal(owner.inspect().paintedAnchors,0);
});
