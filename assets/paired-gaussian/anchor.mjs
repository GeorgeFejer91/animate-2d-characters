// Both paintings map into one moving pose; Gaussian detail never replaces the body.
const smooth=value=>{const t=Math.max(0,Math.min(1,value));return t*t*(3-2*t)};
export function anchorBlend(manifest,sample){
  const pair=manifest.segments[sample.segment],u=Math.max(0,Math.min(1,sample.u));
  return{state:u<=.5?pair.from:pair.to,opacity:1,mix:smooth(u),effect:sample.arc===null?0:Math.sin(Math.PI*u)**2};
}
export async function createPaintedAnchor({THREE,owner,manifest,manifestUrl,signal,queueLoad}){
  const spec=manifest.anchors;
  if(!spec)return null;
  signal?.throwIfAborted?.();
  const states=manifest.states.map(state=>state.id),frames=spec.frames;
  if(spec.maximum_resident!==3||!(spec.fade_seconds>0&&spec.fade_seconds<=.15)||!frames||Object.keys(frames).length!==states.length)throw new Error('Invalid painted anchor manifest');
  for(const id of states){const frame=frames[id];if(!frame||!/^[\w.-]+\.webp$/.test(frame.file)||!(frame.bytes>0&&frame.bytes<=8_000_000)||frame.width!==manifest.canvas_xy[0]||frame.height!==manifest.canvas_xy[1])throw new Error('Invalid painted anchor frame')}
  if(!owner.attachPaint||!owner.retirePaint)throw new Error('Painted anchor owner unavailable');
  const byId=new Map(manifest.states.map(state=>[state.id,state]));
  const controls=manifest.segments.map(pair=>{
    if(pair.paint_warp_gain!==undefined&&(!Number.isFinite(pair.paint_warp_gain)||pair.paint_warp_gain<0||pair.paint_warp_gain>1))throw new Error('Invalid painted warp gain');
    const a=byId.get(pair.from)?.landmarks??{},b=byId.get(pair.to)?.landmarks??{};
    const keys=Object.keys(a).filter(key=>Object.hasOwn(b,key));
    if(keys.length<2||keys.length>32)throw new Error('Painted anchor needs 2–32 common landmark controls');
    return keys.map(key=>{
      if(![a[key],b[key]].every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))throw new Error('Invalid painted anchor landmark');
      return [a[key],b[key]].map(p=>[(p[0]-manifest.canvas_xy[0]/2)/manifest.canvas_xy[1],(manifest.canvas_xy[1]-p[1])/manifest.canvas_xy[1]]);
    });
  });
  const speechNames=manifest.speech_landmarks??[],speechRadius=manifest.speech_radius_px??[12,8],speechAmplitude=manifest.speech_amplitude_px??1;
  if(!Array.isArray(speechNames)||speechNames.length>2||speechNames.some(name=>typeof name!=='string')||
     !Array.isArray(speechRadius)||speechRadius.length!==2||speechRadius.some(value=>!(value>0&&Number.isFinite(value)))||
     !(speechAmplitude>=0&&Number.isFinite(speechAmplitude)&&speechAmplitude/manifest.canvas_xy[1]<.02))throw new Error('Invalid painted anchor speech settings');
  const glslFloat=value=>Number(value).toPrecision(9);
  const aspect=glslFloat(manifest.canvas_xy[1]/manifest.canvas_xy[0]);
  const regularizer=glslFloat((25/manifest.canvas_xy[1])**2);
  const mouthRadiusX=glslFloat(speechRadius[0]/manifest.canvas_xy[0]);
  const mouthRadiusY=glslFloat(speechRadius[1]/manifest.canvas_xy[1]);
  const mouthTravel=glslFloat(speechAmplitude/manifest.canvas_xy[1]);
  const cache=new Map(),failures=new Map(),controller=new AbortController();let disposed=false,wanted=[],pending=null,selected=null,opacity=0;
  const geometry=new THREE.PlaneGeometry(manifest.canvas_xy[0]/manifest.canvas_xy[1],1,32,32);
  const material=new THREE.MeshBasicMaterial({transparent:true,alphaTest:.035,depthWrite:false,side:THREE.DoubleSide});
  const breath={value:0},mouth={value:0},mouthA={value:new THREE.Vector2()},mouthB={value:new THREE.Vector2()},mapB={value:null},mix={value:0},phase={value:0},warpGain={value:1};material.userData.breath=breath;
  const faceA={value:Array.from({length:2},()=>new THREE.Vector2())},faceB={value:Array.from({length:2},()=>new THREE.Vector2())},faceEnabled={value:0};
  const controlCount={value:0},controlSource={value:Array.from({length:32},()=>new THREE.Vector2())},controlTarget={value:Array.from({length:32},()=>new THREE.Vector2())};
  material.onBeforeCompile=shader=>{
    shader.uniforms.anchorBreath=breath;shader.uniforms.anchorMouth=mouth;shader.uniforms.anchorMouthA=mouthA;shader.uniforms.anchorMouthB=mouthB;shader.uniforms.anchorMapB=mapB;shader.uniforms.anchorMix=mix;shader.uniforms.anchorPhase=phase;
    shader.uniforms.anchorControlCount=controlCount;shader.uniforms.anchorControlSource=controlSource;shader.uniforms.anchorControlTarget=controlTarget;
    shader.uniforms.anchorFaceA=faceA;shader.uniforms.anchorFaceB=faceB;shader.uniforms.anchorFaceEnabled=faceEnabled;
    shader.uniforms.anchorWarpGain=warpGain;
    shader.vertexShader='uniform int anchorControlCount;uniform vec2 anchorControlSource[32];uniform vec2 anchorControlTarget[32];uniform float anchorPhase;uniform float anchorWarpGain;varying vec2 anchorUvA;varying vec2 anchorUvB;varying vec2 anchorCanvas;\n'+shader.vertexShader.replace('#include <begin_vertex>',`
      vec3 transformed=vec3(position);
      vec2 q=position.xy+vec2(0.,.5),cc=vec2(0.),ca=vec2(0.),cb=vec2(0.);float total=0.;
      anchorCanvas=q;
      for(int k=0;k<32;k++){if(k>=anchorControlCount)break;vec2 c=mix(anchorControlSource[k],anchorControlTarget[k],anchorPhase);vec2 d=q-c;float w=1./pow(dot(d,d)+${regularizer},2.);cc+=w*c;ca+=w*anchorControlSource[k];cb+=w*anchorControlTarget[k];total+=w;}
      cc/=max(total,1e-12);ca/=max(total,1e-12);cb/=max(total,1e-12);
      float norm=0.,aa=0.,ba=0.,ab=0.,bb=0.;
      for(int k=0;k<32;k++){if(k>=anchorControlCount)break;vec2 c=mix(anchorControlSource[k],anchorControlTarget[k],anchorPhase);vec2 d=q-c;float w=1./pow(dot(d,d)+${regularizer},2.);vec2 s=c-cc,a=anchorControlSource[k]-ca,b=anchorControlTarget[k]-cb;norm+=w*dot(s,s);aa+=w*dot(s,a);ba+=w*(s.x*a.y-s.y*a.x);ab+=w*dot(s,b);bb+=w*(s.x*b.y-s.y*b.x);}
      vec2 v=q-cc;
      vec2 a=norm>1e-12?ca+vec2(aa*v.x-ba*v.y,ba*v.x+aa*v.y)/norm:q+ca-cc;
      vec2 b=norm>1e-12?cb+vec2(ab*v.x-bb*v.y,bb*v.x+ab*v.y)/norm:q+cb-cc;
      a=mix(q,a,anchorWarpGain);b=mix(q,b,anchorWarpGain);
      anchorUvA=vec2(a.x*${aspect}+.5,a.y);
      anchorUvB=vec2(b.x*${aspect}+.5,b.y);
    `);
    shader.fragmentShader='uniform float anchorBreath;uniform float anchorMouth;uniform vec2 anchorMouthA;uniform vec2 anchorMouthB;uniform sampler2D anchorMapB;uniform float anchorMix;uniform float anchorPhase;uniform vec2 anchorFaceA[2];uniform vec2 anchorFaceB[2];uniform float anchorFaceEnabled;varying vec2 anchorUvA;varying vec2 anchorUvB;varying vec2 anchorCanvas;\n'+shader.fragmentShader.replace('#include <map_fragment>',`
      vec2 uvA=anchorUvA,uvB=anchorUvB;
      // Only an authored, separated eye pair enables face protection.
      if(anchorFaceEnabled>.5){
      vec2 eyeA=(anchorFaceA[0]+anchorFaceA[1])*.5,eyeB=(anchorFaceB[0]+anchorFaceB[1])*.5;
      vec2 eye=mix(eyeA,eyeB,anchorPhase),vA=anchorFaceA[1]-anchorFaceA[0],vB=anchorFaceB[1]-anchorFaceB[0],v=mix(vA,vB,anchorPhase),d=anchorCanvas-eye;
      float den=max(dot(v,v),1e-8),ra=dot(v,vA)/den,sa=(v.x*vA.y-v.y*vA.x)/den,rb=dot(v,vB)/den,sb=(v.x*vB.y-v.y*vB.x)/den;
      vec2 headA=eyeA+vec2(ra*d.x-sa*d.y,sa*d.x+ra*d.y),headB=eyeB+vec2(rb*d.x-sb*d.y,sb*d.x+rb*d.y);
      float head=1.-smoothstep(.7,1.3,length((d-vec2(0.,.015))/vec2(.105,.14)));
      uvA=mix(uvA,vec2(headA.x*${aspect}+.5,headA.y),head);uvB=mix(uvB,vec2(headB.x*${aspect}+.5,headB.y),head);
      }
      vec2 faceA=(uvA-anchorMouthA)/vec2(${mouthRadiusX},${mouthRadiusY}),faceB=(uvB-anchorMouthB)/vec2(${mouthRadiusX},${mouthRadiusY});
      uvA.y+=exp(-dot(faceA,faceA)*3.5)*anchorMouth*${mouthTravel};uvB.y+=exp(-dot(faceB,faceB)*3.5)*anchorMouth*${mouthTravel};
      vec4 a=texture2D(map,uvA),b=texture2D(anchorMapB,uvB);
      a*=step(0.,uvA.x)*step(uvA.x,1.)*step(0.,uvA.y)*step(uvA.y,1.);
      b*=step(0.,uvB.x)*step(uvB.x,1.)*step(0.,uvB.y)*step(uvB.y,1.);
      // sRGB anchor textures sample into linear light; blend premultiplied paint.
      float coverage=mix(a.a,b.a,anchorMix);vec3 ink=mix(a.rgb*a.a,b.rgb*b.a,anchorMix);
      diffuseColor*=vec4(coverage>1e-5?ink/coverage:vec3(0.),coverage);
      float paintLightness=dot(diffuseColor.rgb,vec3(.2126,.7152,.0722));diffuseColor.rgb=mix(vec3(paintLightness),diffuseColor.rgb,1.085+.055*anchorBreath)*(1.015+.035*anchorBreath);
    `)
  };
  const mesh=new THREE.Mesh(geometry,material);mesh.visible=false;mesh.userData.anchorActive=false;owner.attachPaint(mesh);
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
      const points=controls[sample.segment];controlCount.value=points.length;
      points.forEach(([a,b],k)=>{
        controlSource.value[k].set(...a);controlTarget.value[k].set(...b);
      });
      phase.value=sample.u;
      warpGain.value=pair.paint_warp_gain??.1;
      const validPoint=point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite);
      const eyeIds=['eye_right','eye_left'];
      faceEnabled.value=[pair.from,pair.to].every(id=>{
        const marks=byId.get(id).landmarks,a=marks?.[eyeIds[0]],b=marks?.[eyeIds[1]];
        return validPoint(a)&&validPoint(b)&&Math.hypot(a[0]-b[0],a[1]-b[1])>1e-3;
      })?1:0;
      if(faceEnabled.value){
        const eyes=id=>eyeIds.map(key=>byId.get(id).landmarks[key]);
        const [a,b]=[eyes(pair.from),eyes(pair.to)];
        const vx=(a[1][0]-a[0][0])*(1-sample.u)+(b[1][0]-b[0][0])*sample.u;
        const vy=(a[1][1]-a[0][1])*(1-sample.u)+(b[1][1]-b[0][1])*sample.u;
        if(Math.hypot(vx,vy)<=1e-3)faceEnabled.value=0;
      }
      if(faceEnabled.value){for(const [id,face] of [[pair.from,faceA],[pair.to,faceB]]){
        const marks=byId.get(id).landmarks;
        eyeIds.forEach((key,k)=>{const p=marks[key];face.value[k].set((p[0]-manifest.canvas_xy[0]/2)/manifest.canvas_xy[1],(manifest.canvas_xy[1]-p[1])/manifest.canvas_xy[1])});
      }}
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
      if(material.map!==entry.texture){material.map=entry.texture;material.needsUpdate=true}
      mapB.value=b?.texture??entry.texture;mix.value=a&&b?blend.mix:a?0:1;
      if(!a)mapB.value=entry.texture;
      material.opacity=opacity;mesh.visible=true;return opacity;
    },
    async settle(){for(let n=0;n<3;n++){pump();if(!pending)break;await pending}},
    inspect(){return{state:selected,opacity:mesh.visible?opacity:0,textureMix:mix.value,phase:phase.value,visible:!disposed&&mesh.visible,resident:cache.size,pending:!!pending,failures:Object.fromEntries(failures),dimensions:mesh.visible?[spec.frames[states[0]].width,spec.frames[states[0]].height]:null}},
    dispose(){if(disposed)return;disposed=true;controller.abort();signal?.removeEventListener?.('abort',onAbort);mesh.visible=false;mesh.userData.anchorActive=false;owner.retirePaint(mesh);geometry.dispose();material.dispose();for(const entry of cache.values())free(entry);cache.clear()},
  };
  signal?.addEventListener?.('abort',onAbort,{once:true});
  wanted=[...new Set([manifest.segments[0].from,manifest.segments[0].to])];
  try{for(const id of wanted)await load(id);signal?.throwIfAborted?.();return api}catch(error){api.dispose();throw error}
}
