// Native-image Gaussian patches transport the whole painting on the paired paths.
const smooth=value=>{const t=Math.max(0,Math.min(1,value));return t*t*(3-2*t)};
// Spatial phase delay uses the host's existing simulation phase. Its envelope
// vanishes at both authored keys and its derivative remains positive.
export function gaussianFlowPhase(phase,midpoint,envelope=Math.sin(Math.PI*phase)**2){
  return phase+.085*Math.sin(midpoint[1]*9+midpoint[0]*6)*envelope;
}
export const gaussianFlowGlsl={
  phase:(phase,midpoint,envelope)=>`(${phase}+.085*sin((${midpoint}).y*9.+(${midpoint}).x*6.)*(${envelope}))`,
  wave:(p,phase)=>`vec2(.022*sin(${p}.y*10.+${phase}*3.14159265),.007*sin(${p}.x*13.-${phase}*3.14159265))`,
};
export function anchorBlend(manifest,sample){
  const pair=manifest.segments[sample.segment],u=Math.max(0,Math.min(1,sample.u));
  return{state:u<=.5?pair.from:pair.to,opacity:1,mix:smooth(u),effect:sample.arc===null?0:Math.sin(Math.PI*u)**2};
}
export async function createPaintedAnchor({THREE,owner,manifest,manifestUrl,signal,queueLoad,paired}){
  const spec=manifest.anchors;
  if(!spec)return null;
  signal?.throwIfAborted?.();
  const states=manifest.states.map(state=>state.id),frames=spec.frames;
  if(spec.maximum_resident!==3||!(spec.fade_seconds>0&&spec.fade_seconds<=.15)||!frames||Object.keys(frames).length!==states.length)throw new Error('Invalid painted anchor manifest');
  for(const id of states){const frame=frames[id];if(!frame||!/^[\w.-]+\.webp$/.test(frame.file)||!(frame.bytes>0&&frame.bytes<=8_000_000)||frame.width!==manifest.canvas_xy[0]||frame.height!==manifest.canvas_xy[1])throw new Error('Invalid painted anchor frame')}
  if(!owner.attachPaint||!owner.retirePaint)throw new Error('Painted anchor owner unavailable');
  const byId=new Map(manifest.states.map(state=>[state.id,state]));
  for(const pair of manifest.segments){
    if(pair.paint_warp_gain!==undefined&&(!Number.isFinite(pair.paint_warp_gain)||pair.paint_warp_gain<0||pair.paint_warp_gain>1))throw new Error('Invalid painted warp gain');
    const a=byId.get(pair.from)?.landmarks??{},b=byId.get(pair.to)?.landmarks??{};
    const keys=Object.keys(a).filter(key=>Object.hasOwn(b,key));
    if(keys.length<2||keys.length>32)throw new Error('Painted anchor needs 2–32 common landmark controls');
    for(const key of keys)if(![a[key],b[key]].every(point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite)))throw new Error('Invalid painted anchor landmark');
  }
  const speechNames=manifest.speech_landmarks??[],speechRadius=manifest.speech_radius_px??[12,8],speechAmplitude=manifest.speech_amplitude_px??1;
  if(!Array.isArray(speechNames)||speechNames.length>2||speechNames.some(name=>typeof name!=='string')||
     !Array.isArray(speechRadius)||speechRadius.length!==2||speechRadius.some(value=>!(value>0&&Number.isFinite(value)))||
     !(speechAmplitude>=0&&Number.isFinite(speechAmplitude)&&speechAmplitude/manifest.canvas_xy[1]<.02))throw new Error('Invalid painted anchor speech settings');
  const cache=new Map(),failures=new Map(),controller=new AbortController();let disposed=false,wanted=[],pending=null,selected=null,opacity=0;
  const geometry=new THREE.PlaneGeometry(manifest.canvas_xy[0]/manifest.canvas_xy[1],1);
  geometry.setAttribute('anchorSlot',new THREE.Float32BufferAttribute(new Float32Array(4),1));
  let patches=null;
  if(paired){
    if(!Number.isInteger(paired.count)||paired.count<1||paired.count>20000||paired.textures?.length!==3||!(paired.stride>0&&paired.stride<=32)||!Number.isInteger(paired.rows)||paired.rows<1)throw new Error('Invalid native Gaussian patches');
    const quad=new THREE.PlaneGeometry(2,2);
    patches=new THREE.InstancedBufferGeometry();patches.index=quad.index;
    for(const [key,attribute] of Object.entries(quad.attributes))patches.setAttribute(key,attribute);
    patches.setAttribute('anchorSlot',new THREE.InstancedBufferAttribute(Float32Array.from({length:paired.count},(_,i)=>i),1));
    patches.instanceCount=paired.count;
  }
  const material=new THREE.MeshBasicMaterial({transparent:true,alphaTest:.0001,depthWrite:false,side:THREE.DoubleSide});
  const breath={value:0},mouth={value:0},mouthA={value:new THREE.Vector2()},mouthB={value:new THREE.Vector2()},mapB={value:null},mix={value:0},phase={value:0},segment={value:0},mode={value:0},effect={value:0};material.userData.breath=breath;
  const number=value=>Number(value).toPrecision(9),aspect=number(manifest.canvas_xy[1]/manifest.canvas_xy[0]);
  const mouthRadiusX=number(speechRadius[0]/manifest.canvas_xy[0]),mouthRadiusY=number(speechRadius[1]/manifest.canvas_xy[1]);
  const mouthTravel=number(speechAmplitude/manifest.canvas_xy[1]);
  const ownedPaths=(paired?.trajectories??[]).map(item=>`
    if(int(anchorSegment)==${item.segment}&&slot>=${item.start_slot}&&slot<${item.end_slot}){
      vec2 pivotA=vec2(${item.pivot_start.map(number)}),pivotB=vec2(${item.pivot_end.map(number)});
      u=gaussianFlowPhase(anchorPhase,.5*(pivotA+pivotB),anchorEffect/.75);
      float angle=${number(item.angle_radians)},theta=u*angle;
      vec2 localB=endpoints.zw-pivotB;
      vec2 unturnedB=vec2(cos(angle)*localB.x+sin(angle)*localB.y,-sin(angle)*localB.x+cos(angle)*localB.y);
      vec2 local=mix(endpoints.xy-pivotA,unturnedB,u);
      p=mix(pivotA,pivotB,u)+anchorRotate(local,theta);
      turn=theta;endTurn=angle;
    }
  `).join('\n');
  // Three's default key stringifies this closure, which is identical for actors
  // whose compiled shader embeds different dimensions, rows, or prop paths.
  const programKey=JSON.stringify(['native-gaussian-paint-v2',manifest.canvas_xy,paired?.rows??1,paired?.stride??1,ownedPaths,speechRadius,speechAmplitude]);
  material.customProgramCacheKey=()=>programKey;
  material.onBeforeCompile=shader=>{
    shader.uniforms.anchorBreath=breath;shader.uniforms.anchorMouth=mouth;shader.uniforms.anchorMouthA=mouthA;shader.uniforms.anchorMouthB=mouthB;shader.uniforms.anchorMapB=mapB;shader.uniforms.anchorMix=mix;shader.uniforms.anchorPhase=phase;
    shader.uniforms.anchorSegment=segment;shader.uniforms.anchorMode=mode;shader.uniforms.anchorEffect=effect;
    shader.uniforms.anchorXY={value:paired?.textures[0]??null};shader.uniforms.anchorStart={value:paired?.textures[1]??null};shader.uniforms.anchorEnd={value:paired?.textures[2]??null};
    shader.vertexShader=`attribute float anchorSlot;uniform sampler2D anchorXY;uniform sampler2D anchorStart;uniform sampler2D anchorEnd;uniform float anchorSegment;uniform float anchorMode;uniform float anchorPhase;uniform float anchorMix;uniform float anchorEffect;varying vec2 anchorUvA;varying vec2 anchorUvB;varying vec2 anchorKernel;varying vec2 anchorPresent;varying float anchorPaintMix;
      float gaussianFlowPhase(float phase,vec2 midpoint,float envelope){return ${gaussianFlowGlsl.phase('phase','midpoint','envelope')};}
      vec2 gaussianFlowWave(vec2 p,float phase){return ${gaussianFlowGlsl.wave('p','phase')};}
      vec2 anchorRotate(vec2 p,float a){return vec2(cos(a)*p.x-sin(a)*p.y,sin(a)*p.x+cos(a)*p.y);}
      `+shader.vertexShader.replace('#include <begin_vertex>',`
      vec3 transformed=vec3(position);
      vec2 q=position.xy+vec2(0.,.5);
      anchorUvA=vec2(q.x*${aspect}+.5,q.y);anchorUvB=anchorUvA;anchorKernel=vec2(0.);anchorPresent=vec2(1.);
      anchorPaintMix=anchorMix;
      if(anchorMode>.5){
        int slot=int(anchorSlot+.1);ivec2 cell=ivec2(slot%256,slot/256+int(anchorSegment)*${paired?.rows??1});
        vec4 endpoints=texelFetch(anchorXY,cell,0);
        anchorPresent=step(vec2(.001),vec2(texelFetch(anchorStart,cell,0).a,texelFetch(anchorEnd,cell,0).a));
        float u=gaussianFlowPhase(anchorPhase,.5*(endpoints.xy+endpoints.zw),anchorEffect/.75),turn=0.,endTurn=0.;vec2 p=mix(endpoints.xy,endpoints.zw,u);
        ${ownedPaths}
        anchorPaintMix=smoothstep(0.,1.,u);
        // The same planted, phase-only wave as the real Spark cloud.
        float planted=smoothstep(.025,.11,p.y);
        p+=anchorEffect*planted*gaussianFlowWave(p,anchorPhase);
        float radius=${number((paired?.stride??1)/manifest.canvas_xy[1]*2.7)}*(1.+.12*anchorEffect);
        vec2 local=position.xy*radius;
        transformed=vec3(p+anchorRotate(local,turn)-vec2(0.,.5),0.);
        vec2 a=endpoints.xy+local,b=endpoints.zw+anchorRotate(local,endTurn);
        anchorUvA=vec2(a.x*${aspect}+.5,a.y);anchorUvB=vec2(b.x*${aspect}+.5,b.y);
        anchorKernel=position.xy*2.7;
      }
    `);
    shader.fragmentShader='uniform float anchorBreath;uniform float anchorMouth;uniform vec2 anchorMouthA;uniform vec2 anchorMouthB;uniform sampler2D anchorMapB;uniform float anchorMix;uniform float anchorMode;uniform float anchorEffect;varying vec2 anchorUvA;varying vec2 anchorUvB;varying vec2 anchorKernel;varying vec2 anchorPresent;varying float anchorPaintMix;\n'+shader.fragmentShader.replace('#include <map_fragment>',`
      vec2 uvA=anchorUvA,uvB=anchorUvB;
      vec2 faceA=(uvA-anchorMouthA)/vec2(${mouthRadiusX},${mouthRadiusY}),faceB=(uvB-anchorMouthB)/vec2(${mouthRadiusX},${mouthRadiusY});
      uvA.y+=exp(-dot(faceA,faceA)*3.5)*anchorMouth*${mouthTravel};uvB.y+=exp(-dot(faceB,faceB)*3.5)*anchorMouth*${mouthTravel};
      vec4 a=texture2D(map,uvA),b=texture2D(anchorMapB,uvB);
      a*=step(0.,uvA.x)*step(uvA.x,1.)*step(0.,uvA.y)*step(uvA.y,1.);
      b*=step(0.,uvB.x)*step(uvB.x,1.)*step(0.,uvB.y)*step(uvB.y,1.);
      a*=anchorPresent.x;b*=anchorPresent.y;
      float coverage=mix(a.a,b.a,anchorPaintMix);vec3 ink=mix(a.rgb*a.a,b.rgb*b.a,anchorPaintMix);
      diffuseColor*=vec4(coverage>1e-5?ink/coverage:vec3(0.),coverage);
      // Native image samples remain sharp inside each moving Gaussian support.
      if(anchorMode>.5){
        // Optical-depth partition prevents overlapping patches from turning a
        // half-transparent edge opaque. 6.20 is the truncated grid kernel mass.
        float weight=exp(-.5*dot(anchorKernel,anchorKernel));
        float mass=6.20*pow(1.+.12*anchorEffect,2.);
        diffuseColor.a=1.-exp(log(max(1.-diffuseColor.a,1e-5))*weight/mass);
      }
      float paintLightness=dot(diffuseColor.rgb,vec3(.2126,.7152,.0722));diffuseColor.rgb=mix(vec3(paintLightness),diffuseColor.rgb,1.085+.055*anchorBreath)*(1.015+.035*anchorBreath);
    `)
  };
  const mesh=new THREE.Mesh(geometry,material);mesh.frustumCulled=false;mesh.visible=false;mesh.userData.anchorActive=false;owner.attachPaint(mesh);
  const free=entry=>{entry.texture.dispose();entry.bitmap.close()};
  async function load(id){
    if(disposed||controller.signal.aborted)return;
    for(const [key,entry] of cache)if(!wanted.includes(key)&&cache.size>=3){cache.delete(key);free(entry)}
    const frame=frames[id],response=await fetch(new URL(frame.file,manifestUrl),{signal:controller.signal});
    if(!response.ok)throw new Error('Painted anchor unavailable: '+id);
    const bytes=await response.arrayBuffer();if(bytes.byteLength!==frame.bytes)throw new Error('Invalid painted anchor length');
    const bitmap=await createImageBitmap(new Blob([bytes],{type:'image/webp'}),{imageOrientation:'flipY',premultiplyAlpha:'none',colorSpaceConversion:'none'});
    if(disposed||controller.signal.aborted){bitmap.close();return}
    if(bitmap.width!==frame.width||bitmap.height!==frame.height){bitmap.close();throw new Error('Invalid painted anchor dimensions')}
    if(!wanted.includes(id)){bitmap.close();return}
    if(cache.size>=3){bitmap.close();return}
    const texture=new THREE.Texture(bitmap);texture.flipY=false;texture.colorSpace=THREE.SRGBColorSpace;texture.generateMipmaps=false;texture.minFilter=texture.magFilter=THREE.LinearFilter;texture.needsUpdate=true;
    cache.set(id,{texture,bitmap});
  }
  function pump(){
    if(disposed||pending||globalThis.document?.hidden)return;
    const id=wanted.find(id=>!cache.has(id)&&!failures.has(id));if(!id)return;
    const task=async()=>{if(disposed||globalThis.document?.hidden)return;try{await load(id)}catch(error){if(!disposed&&!controller.signal.aborted)failures.set(id,error.message)}};
    pending=Promise.resolve().then(()=>queueLoad?queueLoad(task):task()).catch(error=>{if(!disposed&&!controller.signal.aborted)failures.set(id,error.message)}).finally(()=>{pending=null});
  }
  const onAbort=()=>api.dispose();
  const api={
    update(sample,source,visible,animation={}){
      if(disposed)return 0;
      mesh.visible=false;mesh.userData.anchorActive=!!visible;
      if(!visible)return 0;
      const pair=manifest.segments[sample.segment],blend=anchorBlend(manifest,sample);
      const returning=sample.arc?.endsWith('-back')||
        (animation.roundTrip||sample.arc?.endsWith('-roundtrip'))&&animation.phase>.5;
      const direction=returning?-1:1;
      const adjacent=manifest.segments[(sample.segment+direction+manifest.segments.length)%manifest.segments.length];
      const next=direction>0&&adjacent?.from===pair.to?adjacent.to:direction<0&&adjacent?.to===pair.from?adjacent.from:null;
      wanted=[...new Set([pair.from,pair.to,next].filter(Boolean))];selected=blend.state;opacity=blend.opacity;
      phase.value=sample.u;segment.value=sample.segment;effect.value=animation.reducedMotion?0:.75*blend.effect;
      const validPoint=point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite);
      const hasSpeechPoint=speechNames.length>0&&[pair.from,pair.to].every(id=>speechNames.every(name=>validPoint(byId.get(id).landmarks?.[name])));
      if(hasSpeechPoint){for(const [id,center] of [[pair.from,mouthA],[pair.to,mouthB]]){
        const marks=byId.get(id).landmarks,points=speechNames.map(name=>marks[name]);
        const x=points.reduce((sum,p)=>sum+p[0],0)/points.length,y=points.reduce((sum,p)=>sum+p[1],0)/points.length;
        center.value.set(x/manifest.canvas_xy[0],1-y/manifest.canvas_xy[1]);
      }}
      mouth.value=hasSpeechPoint&&animation.speaking&&!animation.reducedMotion?([0,.45,.9,.3,.7,.25,1,.1][animation.mouthFrame%8]??0):0;
      pump();
      const height=source.geometry.parameters.height*source.scale.y;
      mesh.position.copy(source.position);mesh.quaternion.copy(source.quaternion);mesh.scale.setScalar(height);
      material.color.copy(source.material?.color??new THREE.Color(1,1,1));breath.value=source.material?.userData?.breath?.value??0;
      const a=cache.get(pair.from),b=cache.get(pair.to),entry=a??b;
      if(!entry)return 0;
      // A delayed neighbor keeps the available painting intact, never stretched.
      if(!a||!b)phase.value=a?0:1;
      mode.value=a&&b&&patches?1:0;mesh.geometry=mode.value?patches:geometry;
      if(material.map!==entry.texture){material.map=entry.texture;material.needsUpdate=true}
      mapB.value=b?.texture??entry.texture;mix.value=a&&b?blend.mix:a?0:1;
      if(!a)mapB.value=entry.texture;
      material.opacity=opacity;mesh.visible=true;return opacity;
    },
    async settle(){for(let n=0;n<3;n++){pump();if(!pending)break;await pending}},
    inspect(){return{state:selected,opacity:mesh.visible?opacity:0,textureMix:mix.value,phase:phase.value,technique:mode.value?'native-texture-gaussians':'native-anchor-fallback',splatCount:mode.value?paired.count:0,visible:!disposed&&mesh.visible,resident:cache.size,pending:!!pending,failures:Object.fromEntries(failures),dimensions:mesh.visible?[spec.frames[states[0]].width,spec.frames[states[0]].height]:null}},
    dispose(){if(disposed)return;disposed=true;controller.abort();signal?.removeEventListener?.('abort',onAbort);mesh.visible=false;mesh.userData.anchorActive=false;owner.retirePaint(mesh);geometry.dispose();patches?.dispose();material.dispose();for(const entry of cache.values())free(entry);cache.clear()},
  };
  signal?.addEventListener?.('abort',onAbort,{once:true});
  wanted=[...new Set([manifest.segments[0].from,manifest.segments[0].to])];
  try{for(const id of wanted)await load(id);signal?.throwIfAborted?.();return api}catch(error){api.dispose();throw error}
}
