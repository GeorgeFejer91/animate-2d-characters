// One registered Gaussian cloud per actor. The simulation supplies all action time.
import {createPaintedAnchor,anchorBlend,gaussianFlowGlsl} from './anchor.mjs';
const clamp=value=>Math.max(0,Math.min(1,Number.isFinite(value)?value:0));
const RECORD_BYTES=24,TEXTURE_WIDTH=256,MAX_SAMPLES=20000,MAX_SEGMENTS=32,MAX_TRAJECTORIES=64,MAX_TRAJECTORIES_PER_SEGMENT=8;

// CPU reference for inspecting an owned prop's endpoint and midpoint geometry.
export function sampleOwnedTrajectory(trajectory,start,end,phase){
  const u=clamp(phase),angle=trajectory.angle_radians,[ax,ay]=trajectory.pivot_start,[bx,by]=trajectory.pivot_end;
  const rotate=(x,y,radians)=>[x*Math.cos(radians)-y*Math.sin(radians),x*Math.sin(radians)+y*Math.cos(radians)];
  const localEnd=rotate(end[0]-bx,end[1]-by,-angle);
  const local=[(start[0]-ax)*(1-u)+localEnd[0]*u,(start[1]-ay)*(1-u)+localEnd[1]*u];
  const turned=rotate(...local,u*angle);
  return[ax+(bx-ax)*u+turned[0],ay+(by-ay)*u+turned[1]];
}

export function sampleArc(manifest,state){
  if(!manifest?.arcs?.length||!manifest?.segments?.length||!state)throw new Error('Gaussian animation state unavailable');
  const arcName=state.arc;
  if(arcName===null){
    const pose=state.pose;
    const incoming=manifest.arcs.find(arc=>arc.to===pose);
    if(incoming){const key=incoming.segments.at(-1);return{segment:key.segment,u:1,arc:null,pose}}
    const outgoing=manifest.arcs.find(arc=>arc.from===pose);
    if(outgoing)return{segment:outgoing.segments[0].segment,u:0,arc:null,pose};
    throw new Error('Unknown Gaussian main pose: '+pose);
  }
  let reverse=false,arcId=arcName,phase=clamp(state.phase);
  if(state.roundTrip||arcName.endsWith('-roundtrip')){
    arcId=state.roundTrip?arcName:arcName.slice(0,-10);
    reverse=phase>.5;phase=reverse?2*phase-1:2*phase;
  }else if(arcName.endsWith('-back')){
    arcId=arcName.slice(0,-5);reverse=true;
  }
  const arc=manifest.arcs.find(candidate=>candidate.id===arcId);
  if(!arc)throw new Error('Unknown Gaussian arc: '+arcName);
  const time=(reverse?1-phase:phase)*arc.duration;
  const keys=arc.segments;
  const key=keys.find(segment=>time<segment.end-1e-9)??keys.at(-1);
  return{segment:key.segment,u:clamp((time-key.start)/(key.end-key.start)),arc:arcName,pose:state.pose};
}

export function validateGaussianManifest(manifest,variant='desktop'){
  const selected=manifest?.variants?.[variant],canvas=manifest?.canvas_xy;
  if(manifest?.version!==1||manifest.representation!=='paired-gaussian-paint'||
     !Array.isArray(canvas)||canvas.length!==2||canvas.some(n=>!Number.isInteger(n)||n<1||n>4096)||
     !Array.isArray(manifest.states)||!manifest.states.length||
     !Array.isArray(manifest.segments)||manifest.segments.length<1||manifest.segments.length>MAX_SEGMENTS||
     !Array.isArray(manifest.arcs)||!selected||
     !Number.isInteger(selected.sample_count)||selected.sample_count<1||selected.sample_count>MAX_SAMPLES||selected.sample_count%TEXTURE_WIDTH!==0||
     selected.segment_count!==manifest.segments.length||selected.record_bytes!==RECORD_BYTES||
     selected.decoded_bytes!==selected.sample_count*selected.segment_count*RECORD_BYTES||
     !Number.isInteger(selected.bytes)||selected.bytes<1||selected.bytes>8_000_000||
     !Number.isFinite(selected.stride_px)||selected.stride_px<=0||selected.stride_px>32||
     typeof selected.file!=='string'||!/^[\w.-]+\.bin\.gz$/.test(selected.file))throw new Error('Invalid Gaussian animation manifest');
  const states=new Set(manifest.states.map(item=>item.id));
  if(states.size!==manifest.states.length||manifest.segments.some(segment=>!states.has(segment.from)||!states.has(segment.to)))throw new Error('Invalid Gaussian state graph');
  for(const arc of manifest.arcs){
    if(!(arc.duration>0)||!Array.isArray(arc.segments)||!arc.segments.length)throw new Error('Invalid Gaussian arc');
    let previous=0;
    for(const key of arc.segments){
      if(!Number.isInteger(key.segment)||key.segment<0||key.segment>=selected.segment_count||
         !Number.isFinite(key.start)||!Number.isFinite(key.end)||Math.abs(key.start-previous)>1e-5||key.end<=key.start||key.end>arc.duration+1e-5)throw new Error('Invalid Gaussian segment timing');
      previous=key.end;
    }
    if(Math.abs(previous-arc.duration)>1e-5)throw new Error('Incomplete Gaussian arc');
  }
  const trajectories=selected.trajectories??[];
  if(!Array.isArray(trajectories)||trajectories.length>MAX_TRAJECTORIES)throw new Error('Invalid Gaussian trajectories');
  const ranges=Array.from({length:selected.segment_count},()=>[]);
  for(const item of trajectories){
    const pivot=value=>Array.isArray(value)&&value.length===2&&value.every(n=>Number.isFinite(n)&&Math.abs(n)<=4);
    if(!item||!Number.isInteger(item.segment)||item.segment<0||item.segment>=selected.segment_count||
       !Number.isInteger(item.start_slot)||item.start_slot<0||
       !Number.isInteger(item.end_slot)||item.end_slot<=item.start_slot||item.end_slot>selected.sample_count||
       !pivot(item.pivot_start)||!pivot(item.pivot_end)||
       !Number.isFinite(item.angle_radians)||Math.abs(item.angle_radians)>Math.PI)
      throw new Error('Invalid Gaussian trajectory');
    const group=ranges[item.segment];
    if(group.length>=MAX_TRAJECTORIES_PER_SEGMENT||group.some(([first,last])=>item.start_slot<last&&item.end_slot>first))
      throw new Error('Overlapping or excessive Gaussian trajectories');
    group.push([item.start_slot,item.end_slot]);
  }
  return selected;
}

export function unpackGaussianRecords(manifest,variant,buffer){
  const selected=validateGaussianManifest(manifest,variant);
  if(buffer.byteLength!==selected.decoded_bytes)throw new Error('Invalid Gaussian record length');
  const count=selected.sample_count,total=count*selected.segment_count,view=new DataView(buffer);
  const xy=new Float32Array(total*4),start=new Uint8Array(total*4),end=new Uint8Array(total*4);
  for(let slot=0;slot<total;slot++){
    const record=slot*RECORD_BYTES,base=slot*4;
    for(let axis=0;axis<4;axis++){
      const value=view.getFloat32(record+axis*4,true);
      if(!Number.isFinite(value)||Math.abs(value)>4)throw new Error('Non-finite or unbounded Gaussian coordinate');
      xy[base+axis]=value;
      start[base+axis]=view.getUint8(record+16+axis);
      end[base+axis]=view.getUint8(record+20+axis);
    }
  }
  return{xy,start,end,count,rows:count/TEXTURE_WIDTH,segments:selected.segment_count,stride:selected.stride_px};
}

async function loadRecords(url,selected,signal){
  if(typeof DecompressionStream!=='function')throw new Error('Native gzip decoding unavailable');
  const response=await fetch(url,{signal});
  if(!response.ok)throw new Error('Gaussian animation data unavailable');
  const compressed=await response.arrayBuffer();
  if(compressed.byteLength!==selected.bytes)throw new Error('Invalid compressed Gaussian length');
  const reader=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip')).getReader();
  const decoded=new Uint8Array(selected.decoded_bytes);let offset=0;
  try{
    while(true){
      const {value,done}=await reader.read();if(done)break;
      if(offset+value.length>decoded.length)throw new Error('Gaussian gzip exceeds declared size');
      decoded.set(value,offset);offset+=value.length;
    }
  }catch(error){await reader.cancel().catch(()=>{});throw error}
  signal?.throwIfAborted?.();
  if(offset!==selected.decoded_bytes)throw new Error('Invalid decoded Gaussian length');
  return decoded.buffer;
}

export async function createGaussianActor({THREE,owner,manifestUrl,variant='desktop',signal,queueLoad,anchorPaint=true}){
  signal?.throwIfAborted?.();
  if(!owner?.attach||!owner?.retire||!owner?.SplatMesh||!owner?.dyno)throw new Error('Gaussian owner unavailable');
  const url=new URL(manifestUrl,import.meta.url);
  const response=await fetch(url,{signal});
  if(!response.ok)throw new Error('Gaussian animation manifest unavailable');
  const manifest=await response.json(),selected=validateGaussianManifest(manifest,variant);
  const data=unpackGaussianRecords(manifest,variant,await loadRecords(new URL(selected.file,url),selected,signal));
  signal?.throwIfAborted?.();
  const {dyno,SplatMesh}=owner,textures=[];
  const glslNumber=value=>Number(value).toPrecision(9);
  const trajectoryCode=segmentExpression=>(selected.trajectories??[]).map(item=>`
    if(int(${segmentExpression})==${item.segment}&&slot>=${item.start_slot}&&slot<${item.end_slot}){
      vec2 pivotA=vec2(${item.pivot_start.map(glslNumber).join(',')}),pivotB=vec2(${item.pivot_end.map(glslNumber).join(',')});
      u=${gaussianFlowGlsl.phase('phase','.5*(pivotA+pivotB)','envelope')};
      float angle=${glslNumber(item.angle_radians)},theta=u*angle;
      vec2 localB=endpoints.zw-pivotB;
      vec2 unturnedB=vec2(cos(angle)*localB.x+sin(angle)*localB.y,-sin(angle)*localB.x+cos(angle)*localB.y);
      vec2 local=mix(endpoints.xy-pivotA,unturnedB,u);
      p=mix(pivotA,pivotB,u)+vec2(cos(theta)*local.x-sin(theta)*local.y,sin(theta)*local.x+cos(theta)*local.y);
    }
  `).join('\n');
  const stateById=new Map(manifest.states.map(item=>[item.id,item]));
  const speechNames=Array.isArray(manifest.speech_landmarks)?manifest.speech_landmarks:[];
  const speechRadius=manifest.speech_radius_px??[data.stride*8,data.stride*5];
  const speechAmplitude=(manifest.speech_amplitude_px??2)/manifest.canvas_xy[1];
  if(speechNames.length>2||speechNames.some(name=>typeof name!=='string')||speechRadius.length!==2||speechRadius.some(n=>!(n>0))||!(speechAmplitude>=0&&speechAmplitude<.02))throw new Error('Invalid speech landmark settings');
  let mesh=null,paint=null,attached=false,disposed=false,failure='',readyAfterSort=null,lastKey='';
  const releaseTextures=()=>{for(const texture of textures)texture.dispose()};
  try{
    for(const [array,type] of [[data.xy,THREE.FloatType],[data.start,THREE.UnsignedByteType],[data.end,THREE.UnsignedByteType]]){
      const texture=new THREE.DataTexture(array,TEXTURE_WIDTH,data.rows*data.segments,THREE.RGBAFormat,type);
      texture.minFilter=texture.magFilter=THREE.NearestFilter;
      texture.wrapS=texture.wrapT=THREE.ClampToEdgeWrapping;
      texture.generateMipmaps=false;texture.flipY=false;texture.needsUpdate=true;
      textures.push(texture);
    }
    const segment=dyno.dynoFloat(0),blend=dyno.dynoFloat(0),strength=dyno.dynoFloat(1),painted=dyno.dynoFloat(0),mouth=dyno.dynoFloat(0),mouthCenter=dyno.dynoVec2(new THREE.Vector2()),tint=dyno.dynoVec3(new THREE.Vector3(1,1,1)),breath=dyno.dynoFloat(0);
    const modifier=dyno.dynoBlock({gsplat:dyno.Gsplat},{gsplat:dyno.Gsplat},({gsplat})=>({gsplat:new dyno.Dyno({
      inTypes:{gsplat:dyno.Gsplat,segment:'float',blend:'float',strength:'float',painted:'float',mouth:'float',mouthCenter:'vec2',tint:'vec3',breath:'float',xy:'sampler2D',start:'sampler2D',end:'sampler2D'},
      outTypes:{gsplat:dyno.Gsplat},
      statements:({inputs:i,outputs:o})=>dyno.unindentLines(`
        ${o.gsplat}=${i.gsplat};
        ivec2 cell=ivec2(${i.gsplat}.center.xy+vec2(.1));
        int slot=cell.x+cell.y*${TEXTURE_WIDTH};
        cell.y+=int(${i.segment})*${data.rows};
        vec4 endpoints=texelFetch(${i.xy},cell,0);
        vec4 paintA=texelFetch(${i.start},cell,0),paintB=texelFetch(${i.end},cell,0);
        float phase=clamp(${i.blend},0.,1.),envelope=${i.strength}*${i.painted}/.75;
        float u=${gaussianFlowGlsl.phase('phase','.5*(endpoints.xy+endpoints.zw)','envelope')};
        vec2 p=mix(endpoints.xy,endpoints.zw,u);
        ${trajectoryCode(i.segment)}
        float planted=smoothstep(.025,.11,p.y);
        float flow=${i.strength}*planted*${i.painted};
        p+=flow*${gaussianFlowGlsl.wave('p','phase')};
        ${o.gsplat}.scales.xy*=1.+flow*.45;
        vec2 face=(p-${i.mouthCenter})/vec2(${speechRadius[0]/manifest.canvas_xy[1]},${speechRadius[1]/manifest.canvas_xy[1]});
        float lip=exp(-dot(face,face)*3.5)*${i.mouth};
        p.y-=lip*${speechAmplitude};
        ${o.gsplat}.center=vec3(p,0.);
        vec3 linearA=mix(paintA.rgb/12.92,pow((paintA.rgb+.055)/1.055,vec3(2.4)),step(vec3(.04045),paintA.rgb));
        vec3 linearB=mix(paintB.rgb/12.92,pow((paintB.rgb+.055)/1.055,vec3(2.4)),step(vec3(.04045),paintB.rgb));
        float paintPhase=mix(u,smoothstep(0.,1.,u),${i.painted});
        float alpha=mix(paintA.a,paintB.a,paintPhase);
        vec3 premul=mix(linearA*paintA.a,linearB*paintB.a,paintPhase);
        vec3 linear=alpha>1e-5?premul/alpha:vec3(0.);
        linear*=${i.tint};
        float lightness=dot(linear,vec3(.2126,.7152,.0722));
        linear=mix(vec3(lightness),linear,1.085+.055*${i.breath})*(1.015+.035*${i.breath});
        vec3 srgb=mix(linear*12.92,1.055*pow(max(linear,vec3(0.)),vec3(1./2.4))-.055,step(vec3(.0031308),linear));
        // Spark decodes Gsplat RGB as sRGB during rendering.
        ${o.gsplat}.rgba=vec4(srgb,alpha);
        ${o.gsplat}.rgba.a*=${i.strength}*mix(1.,.18,${i.painted});
      `),
    }).apply({gsplat,segment,blend,strength,painted,mouth,mouthCenter,tint,breath,xy:dyno.dynoSampler2D(textures[0]),start:dyno.dynoSampler2D(textures[1]),end:dyno.dynoSampler2D(textures[2])}).gsplat}));
    mesh=new SplatMesh({maxSplats:data.count,lod:false,enableLod:false,editable:false,raycastable:false,
      objectModifier:modifier,constructSplats:splats=>{
        const center=new THREE.Vector3(),scale=new THREE.Vector3(data.stride/manifest.canvas_xy[1]*.65,data.stride/manifest.canvas_xy[1]*.65,.0008),rotation=new THREE.Quaternion(),white=new THREE.Color(1,1,1);
        for(let slot=0;slot<data.count;slot++){
          center.set(slot%TEXTURE_WIDTH,Math.floor(slot/TEXTURE_WIDTH),0);
          splats.pushSplat(center,scale,rotation,1,white);
        }
      }});
    await mesh.initialized;signal?.throwIfAborted?.();
    mesh.visible=false;owner.attach(mesh);attached=true;
    mesh.updateGenerator?.();
    if(anchorPaint)paint=await createPaintedAnchor({THREE,owner,manifest,manifestUrl:url,signal,queueLoad,
      paired:{count:data.count,rows:data.rows,stride:data.stride,textures,trajectories:selected.trajectories}});
    const onAbort=()=>{api.dispose()};
    const api={
      update(state,sourceMesh,{visible=true,reducedMotion=false}={}){
        if(disposed||failure||!owner.inspect().ready||!state||!sourceMesh){if(mesh)mesh.visible=false;paint?.update(null,sourceMesh,false);return false}
        try{
          if(!visible){mesh.visible=false;paint?.update(null,sourceMesh,false);readyAfterSort=null;return false}
          const sample=sampleArc(manifest,state),height=sourceMesh.geometry?.parameters?.height;
          if(!(height>0)||!(sourceMesh.scale?.y>0))throw new Error('Gaussian source height unavailable');
          const anchorOpacity=paint?.update(sample,sourceMesh,true,{...state,reducedMotion})??0;
          painted.value=anchorOpacity>0?1:0;
          strength.value=anchorOpacity>0?(reducedMotion?0:.75*anchorBlend(manifest,sample).effect):1;
          const color=sourceMesh.material?.color,paintBreath=sourceMesh.material?.userData?.breath?.value??0;
          const key=[sample.segment,sample.u,anchorOpacity,state.speaking,state.mouthFrame,reducedMotion,sourceMesh.position.x,sourceMesh.position.y,sourceMesh.position.z,sourceMesh.scale.y,sourceMesh.rotation.x,sourceMesh.rotation.y,sourceMesh.rotation.z,color?.r,color?.g,color?.b,paintBreath].join(':');
          if(key!==lastKey){
            segment.value=sample.segment;blend.value=sample.u;
            tint.value.set(color?.r??1,color?.g??1,color?.b??1);breath.value=paintBreath;
            const pair=manifest.segments[sample.segment];
            const point=(id,name)=>stateById.get(id)?.landmarks?.[name];
            const source=speechNames.map(name=>point(pair.from,name)),target=speechNames.map(name=>point(pair.to,name));
            const hasSpeechPoint=speechNames.length>0&&source.every(Array.isArray)&&target.every(Array.isArray);
            if(hasSpeechPoint){
              const center=points=>points.reduce((sum,point)=>[sum[0]+point[0]/points.length,sum[1]+point[1]/points.length],[0,0]);
              const from=center(source),to=center(target);
              mouthCenter.value.set(((from[0]+(to[0]-from[0])*sample.u)-manifest.canvas_xy[0]/2)/manifest.canvas_xy[1],(manifest.canvas_xy[1]-(from[1]+(to[1]-from[1])*sample.u))/manifest.canvas_xy[1]);
            }
            mouth.value=hasSpeechPoint&&state.speaking&&!reducedMotion?([0,.45,.9,.3,.7,.25,1,.1][state.mouthFrame%8]??0):0;
            mesh.position.copy(sourceMesh.position);mesh.position.y=sourceMesh.position.y-height*sourceMesh.scale.y/2;
            mesh.quaternion.copy(sourceMesh.quaternion);
            mesh.scale.setScalar(height*sourceMesh.scale.y);
            mesh.needsUpdate=true;lastKey=key;
          }
          mesh.visible=strength.value>.001;
          if(readyAfterSort===null)readyAfterSort=owner.inspect().startedUpdates+1;
          return api.inspect().visible;
        }catch(error){failure=error.message||String(error);mesh.visible=false;paint?.update(null,sourceMesh,false);return false}
      },
      inspect(){const status=owner.inspect(),anchor=paint?.inspect()??null;return{ready:!disposed&&!failure&&status.ready,visible:!disposed&&!failure&&status.ready&&(anchor?.visible||mesh.visible&&readyAfterSort!==null&&status.completedUpdates>=readyAfterSort&&status.activeSplats>0),pending:status.pending,failure:failure||status.failure,variant,id:manifest.id,count:data.count,segmentCount:data.segments,bytes:selected.decoded_bytes,segment:segment.value,blend:blend.value,anchor,trajectoryCount:selected.trajectories?.length??0,activeTrajectories:selected.trajectories?.filter(item=>item.segment===segment.value)??[]}},
      settle:async()=>{await paint?.settle()},
      dispose(){if(disposed)return;disposed=true;signal?.removeEventListener?.('abort',onAbort);paint?.dispose();owner.retire(mesh,releaseTextures)},
    };
    signal?.addEventListener?.('abort',onAbort,{once:true});
    if(signal?.aborted)api.dispose();
    return api;
  }catch(error){
    paint?.dispose();
    if(mesh){if(attached)owner.retire(mesh,releaseTextures);else{mesh.dispose?.();releaseTextures()}}
    else releaseTextures();
    throw error;
  }
}
