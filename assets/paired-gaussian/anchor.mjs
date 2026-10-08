// Original paint follows named controls; splats cover the brief texture handoff.
const smooth=value=>{const t=Math.max(0,Math.min(1,value));return t*t*(3-2*t)};
export function anchorBlend(manifest,sample){
  const pair=manifest.segments[sample.segment],u=Math.max(0,Math.min(1,sample.u));
  let duration=Infinity;
  for(const arc of manifest.arcs)for(const key of arc.segments)if(key.segment===sample.segment)duration=Math.min(duration,key.end-key.start);
  const width=Math.min(.45,(manifest.anchors?.fade_seconds??.09)/duration);
  return{state:u<=.5?pair.from:pair.to,opacity:sample.arc===null?1:smooth(Math.abs(u-.5)/width)};
}
export async function createPaintedAnchor({THREE,owner,manifest,manifestUrl,signal,queueLoad}){
  signal?.throwIfAborted?.();
  const spec=manifest.anchors;
  if(!spec)return null;
  const states=manifest.states.map(state=>state.id),frames=spec.frames;
  if(spec.maximum_resident!==3||!(spec.fade_seconds>0&&spec.fade_seconds<=.15)||!frames||Object.keys(frames).length!==states.length)throw new Error('Invalid painted anchor manifest');
  for(const id of states){const frame=frames[id];if(!frame||!/^[\w.-]+\.webp$/.test(frame.file)||!(frame.bytes>0&&frame.bytes<=8_000_000)||frame.width!==manifest.canvas_xy[0]||frame.height!==manifest.canvas_xy[1])throw new Error('Invalid painted anchor frame')}
  if(!owner.attachPaint||!owner.retirePaint)throw new Error('Painted anchor owner unavailable');
  const byId=new Map(manifest.states.map(state=>[state.id,state]));
  const controls=manifest.segments.map(pair=>{
    const a=byId.get(pair.from)?.landmarks??{},b=byId.get(pair.to)?.landmarks??{};
    const keys=Object.keys(a).filter(key=>Object.hasOwn(b,key));
    if(keys.length<2||keys.length>32)throw new Error('Painted anchor needs 2–32 common landmark controls');
    return keys.map(key=>{
      if(![a[key],b[key]].every(point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite)))throw new Error('Invalid painted anchor landmark');
      return[a[key],b[key]].map(point=>[(point[0]-manifest.canvas_xy[0]/2)/manifest.canvas_xy[1],(manifest.canvas_xy[1]-point[1])/manifest.canvas_xy[1]]);
    });
  });
  const speechNames=manifest.speech_landmarks??[],speechRadius=manifest.speech_radius_px??[12,8],speechAmplitude=manifest.speech_amplitude_px??1;
  if(!Array.isArray(speechNames)||speechNames.length>2||speechNames.some(name=>typeof name!=='string')||
     !Array.isArray(speechRadius)||speechRadius.length!==2||speechRadius.some(value=>!(value>0))||
     !(speechAmplitude>=0&&speechAmplitude/manifest.canvas_xy[1]<.02))throw new Error('Invalid painted anchor speech settings');
  const cache=new Map(),failures=new Map(),controller=new AbortController();let disposed=false,wanted=[],pending=null,selected=null,opacity=0;
  const geometry=new THREE.PlaneGeometry(manifest.canvas_xy[0]/manifest.canvas_xy[1],1,32,32);
  const material=new THREE.MeshBasicMaterial({transparent:true,alphaTest:.035,depthWrite:false,side:THREE.DoubleSide});
  const breath={value:0},mouth={value:0},mouthCenter={value:new THREE.Vector2()};material.userData.breath=breath;
  const controlCount={value:0},controlSource={value:Array.from({length:32},()=>new THREE.Vector2())},controlTarget={value:Array.from({length:32},()=>new THREE.Vector2())};
  material.onBeforeCompile=shader=>{
    shader.uniforms.anchorBreath=breath;shader.uniforms.anchorMouth=mouth;shader.uniforms.anchorMouthCenter=mouthCenter;
    shader.uniforms.anchorControlCount=controlCount;shader.uniforms.anchorControlSource=controlSource;shader.uniforms.anchorControlTarget=controlTarget;
    shader.vertexShader='uniform int anchorControlCount;uniform vec2 anchorControlSource[32];uniform vec2 anchorControlTarget[32];\n'+shader.vertexShader.replace('#include <begin_vertex>',`
      vec3 transformed=vec3(position);
      vec2 q=position.xy+vec2(0.,.5),cs=vec2(0.),ct=vec2(0.);float total=0.;
      for(int k=0;k<32;k++){if(k>=anchorControlCount)break;vec2 d=q-anchorControlSource[k];float w=1./pow(dot(d,d)+${(25/manifest.canvas_xy[1])**2},2.);cs+=w*anchorControlSource[k];ct+=w*anchorControlTarget[k];total+=w;}
      cs/=max(total,1e-12);ct/=max(total,1e-12);
      float norm=0.,a=0.,b=0.;
      for(int k=0;k<32;k++){if(k>=anchorControlCount)break;vec2 d=q-anchorControlSource[k];float w=1./pow(dot(d,d)+${(25/manifest.canvas_xy[1])**2},2.);vec2 s=anchorControlSource[k]-cs,t=anchorControlTarget[k]-ct;norm+=w*dot(s,s);a+=w*dot(s,t);b+=w*(s.x*t.y-s.y*t.x);}
      vec2 v=q-cs;vec2 p=norm>1e-12?ct+vec2(a*v.x-b*v.y,b*v.x+a*v.y)/norm:q+ct-cs;
      transformed.xy=p-vec2(0.,.5);
    `);
    const map=THREE.ShaderChunk.map_fragment.replaceAll('vMapUv','paintUv');
    shader.fragmentShader='uniform float anchorBreath;uniform float anchorMouth;uniform vec2 anchorMouthCenter;\n'+shader.fragmentShader.replace('#include <map_fragment>',
      `vec2 paintUv=vMapUv;vec2 face=(paintUv-anchorMouthCenter)/vec2(${speechRadius[0]/manifest.canvas_xy[0]},${speechRadius[1]/manifest.canvas_xy[1]});paintUv.y+=exp(-dot(face,face)*3.5)*anchorMouth*${speechAmplitude/manifest.canvas_xy[1]};\n${map}\nfloat paintLightness=dot(diffuseColor.rgb,vec3(.2126,.7152,.0722));diffuseColor.rgb=mix(vec3(paintLightness),diffuseColor.rgb,1.085+.055*anchorBreath)*(1.015+.035*anchorBreath);`)
  };
  const mesh=new THREE.Mesh(geometry,material);mesh.visible=false;mesh.userData.anchorActive=false;owner.attachPaint(mesh);
  const free=entry=>{entry.texture.dispose();entry.bitmap.close()};
  async function load(id){
    if(disposed||controller.signal.aborted)return;
    // Bound decoded bitmaps, including the one about to be created.
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
    pending=Promise.resolve().then(()=>queueLoad?queueLoad(task):task()).catch(error=>{
      if(!disposed&&!controller.signal.aborted)failures.set(id,error?.message||String(error));
    }).finally(()=>{pending=null});
  }
  const onAbort=()=>api.dispose();
  const api={
    update(sample,source,visible,animation={}){
      if(disposed)return 0;
      mesh.visible=false;mesh.userData.anchorActive=!!visible;
      if(!visible)return 0;
      const pair=manifest.segments[sample.segment],blend=anchorBlend(manifest,sample);
      wanted=[...new Set([blend.state,pair.from,pair.to])];selected=blend.state;opacity=blend.opacity;
      const controlPairs=controls[sample.segment];controlCount.value=controlPairs.length;
      controlPairs.forEach(([a,b],index)=>{
        controlSource.value[index].set(...(selected===pair.from?a:b));
        controlTarget.value[index].set(a[0]+(b[0]-a[0])*sample.u,a[1]+(b[1]-a[1])*sample.u);
      });
      const marks=manifest.states.find(state=>state.id===selected)?.landmarks;
      const points=speechNames.map(name=>marks?.[name]);
      const hasSpeechPoint=points.length>0&&points.every(point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite));
      if(hasSpeechPoint){
        const center=points.reduce((sum,point)=>[sum[0]+point[0]/points.length,sum[1]+point[1]/points.length],[0,0]);
        mouthCenter.value.set(center[0]/manifest.canvas_xy[0],1-center[1]/manifest.canvas_xy[1]);
      }
      mouth.value=hasSpeechPoint&&animation.speaking&&!animation.reducedMotion?([0,.45,.9,.3,.7,.25,1,.1][animation.mouthFrame%8]??0):0;
      pump();
      const height=source.geometry.parameters.height*source.scale.y;
      mesh.position.copy(source.position);mesh.quaternion.copy(source.quaternion);mesh.scale.setScalar(height);
      material.color.copy(source.material?.color??new THREE.Color(1,1,1));breath.value=source.material?.userData?.breath?.value??0;
      const entry=cache.get(selected);
      if(!entry||opacity<=.001)return 0;
      if(material.map!==entry.texture){material.map=entry.texture;material.needsUpdate=true}
      material.opacity=opacity;mesh.visible=true;return opacity;
    },
    async settle(){for(let n=0;n<3;n++){pump();if(!pending)break;await pending}},
    inspect(){return{state:selected,opacity:mesh.visible?opacity:0,visible:!disposed&&mesh.visible,resident:cache.size,pending:!!pending,failures:Object.fromEntries(failures),dimensions:mesh.visible?[frames[selected].width,frames[selected].height]:null}},
    dispose(){if(disposed)return;disposed=true;controller.abort();signal?.removeEventListener?.('abort',onAbort);mesh.visible=false;mesh.userData.anchorActive=false;owner.retirePaint(mesh);geometry.dispose();material.dispose();for(const entry of cache.values())free(entry);cache.clear()},
  };
  signal?.addEventListener?.('abort',onAbort,{once:true});
  wanted=[states[0]];
  try{await load(states[0]);signal?.throwIfAborted?.();return api}catch(error){api.dispose();throw error}
}
