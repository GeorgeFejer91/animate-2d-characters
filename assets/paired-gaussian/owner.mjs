// Host-owned Spark lifetime for several paired Gaussian actors in one scene.
// Supply the host's licensed, pinned Spark module; this starter never downloads one.
export async function createGaussianOwner({renderer,scene,signal,sparkModule,moduleURL,nowMs=()=>performance.now()}){
  if(!sparkModule&&!moduleURL)throw new Error('Provide a pinned Spark module or local module URL');
  const {SparkRenderer,SplatMesh,dyno}=sparkModule??await import(moduleURL);
  signal?.throwIfAborted?.();
  const spark=new SparkRenderer({renderer,autoUpdate:false,enableLod:false,enableDriveLod:false,enableLodFetching:false,
    minSortIntervalMs:0,maxStdDev:Math.sqrt(5),maxPixelRadius:48,depthTest:true,depthWrite:false});
  spark.visible=false;scene.add(spark);
  const meshes=new Set(),paints=new Set(),retired=new Map(),freed=new WeakSet();
  let paintDepth=null;
  // Three r186 transparent render-item z is homogeneous clip Z (no / W).
  // Keep the Spark batch in those units between admitted paint planes.
  // Hosts with a custom sorter must compose this comparator.
  const transparentSort=(a,b)=>a.groupOrder-b.groupOrder||a.renderOrder-b.renderOrder||
    (b.object===spark&&paintDepth!==null?paintDepth:b.z)-(a.object===spark&&paintDepth!==null?paintDepth:a.z)||a.id-b.id;
  let pending=null,lastUpdate=-Infinity,startedUpdates=0,completedUpdates=0,failure='',disposed=false,disposePromise=null;
  function hide(){spark.visible=false;for(const mesh of meshes)mesh.visible=false;for(const mesh of paints){mesh.visible=false;mesh.userData.anchorActive=false}}
  function fail(error){failure=error?.message||String(error);hide()}
  function flushRetired(){
    if(pending)return;
    for(const [mesh,cleanup] of retired){
      retired.delete(mesh);freed.add(mesh);
      try{mesh.dispose?.()}catch(error){fail(error)}
      try{cleanup?.()}catch(error){fail(error)}
    }
  }
  const owner={
    spark,SplatMesh,dyno,
    attachPaint(mesh){if(disposed||failure)throw new Error('Gaussian paint owner unavailable');if(!paints.size)renderer.setTransparentSort?.(transparentSort);paints.add(mesh);scene.add(mesh);return mesh},
    retirePaint(mesh){if(!paints.delete(mesh))return;mesh.visible=false;scene.remove(mesh);if(!paints.size){paintDepth=null;renderer.setTransparentSort?.(null)}},
    attach(mesh){if(disposed||failure)throw new Error('Gaussian owner unavailable');if(retired.has(mesh)||freed.has(mesh))throw new Error('Retired splat cannot be attached');if(!meshes.has(mesh)){meshes.add(mesh);scene.add(mesh)}return mesh},
    retire(mesh,cleanup){
      if(!mesh||retired.has(mesh)||freed.has(mesh))return;
      meshes.delete(mesh);mesh.visible=false;scene.remove(mesh);retired.set(mesh,cleanup);flushRetired();
    },
    update(camera,rate=60){
      if(disposed||failure||!camera)return null;
      camera.updateMatrixWorld?.(true);
      const anchors=[...paints].filter(mesh=>mesh.userData.anchorActive);
      paintDepth=anchors.length?anchors.reduce((sum,mesh)=>{mesh.updateMatrixWorld(true);const p=mesh.getWorldPosition(camera.position.clone()).applyMatrix4(camera.matrixWorldInverse),e=camera.projectionMatrix.elements;return sum+e[2]*p.x+e[6]*p.y+e[10]*p.z+e[14]},0)/anchors.length:null;
      const visible=[...meshes].filter(mesh=>mesh.visible);
      spark.visible=visible.length>0;
      if(!visible.length||pending)return pending;
      try{
        const hz=Math.max(1,Math.min(60,Number.isFinite(rate)?rate:60)),now=nowMs();
        if(now-lastUpdate<1000/hz)return null;
        lastUpdate=now;
        for(const mesh of visible)mesh.updateMatrixWorld?.(true);
        spark.setDirty?.();startedUpdates++;
        pending=Promise.resolve().then(()=>spark.update({scene,camera})).then(()=>{completedUpdates++}).catch(fail).finally(()=>{pending=null;flushRetired()});
        return pending;
      }catch(error){fail(error);return null}
    },
    inspect(){return{ready:!disposed&&!failure,visible:!disposed&&spark.visible,pending:!!pending,meshes:meshes.size,paintedAnchors:paints.size,retired:retired.size,activeSplats:spark.activeSplats||0,startedUpdates,completedUpdates,failure,disposed}},
    dispose(){
      if(disposePromise)return disposePromise;
      disposed=true;hide();scene.remove(spark);
      for(const mesh of [...paints])owner.retirePaint(mesh);
      for(const mesh of [...meshes])owner.retire(mesh);
      signal?.removeEventListener?.('abort',onAbort);
      disposePromise=Promise.resolve(pending).then(()=>{flushRetired();spark.dispose()}).catch(fail);
      return disposePromise;
    },
  };
  const onAbort=()=>{void owner.dispose()};
  signal?.addEventListener?.('abort',onAbort,{once:true});
  if(signal?.aborted){await owner.dispose();signal.throwIfAborted()}
  return owner;
}
