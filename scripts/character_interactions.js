/* Planted reactions; the host owns routes, events and movement. */
globalThis.CharacterInteractions=(()=>{
 const point=(row,col,ms,role)=>({row,col,ms,role});
 function request(n,names,m,options={}){
  names=Array.isArray(names)?names:[names];
  if(!n||!m?.interactions||!names.length||names.some(s=>s==='look'?!m.interactions.look:!m.interactions.states[s]))return false;
  n.interactionRequest={names:[...names],options};return true;
 }
 function plan(n,m,job){
  const from=n.touristFacing||'down',frames=[],phase=Math.min(7,Math.max(0,n.spriteFrame||0));
  const put=(p,role)=>frames.push({...p,role}),b=m.bridges;
  for(let col=phase+1;col<8;col++)put(point(m.walks[from].row,col,80),'settle');
  if(from==='down')for(const col of b.down.stop_cols)put(point(b.down.row,col,b.down.frame_ms),'settle');
  else for(const p of m.transitions[from+'-to-down'].frames.slice(0,-b.down.start_cols.length))put(p,'settle');
  const idle=m.interactions.states.idle,neutral=()=>put(point(idle.row,0,120),'reaction');neutral();
  for(const name of job.names){
   if(name==='look'){
    const cells=m.interactions.look.frames,target=((job.options.lookIndex??8)%16+16)%16,delta=((target-8+24)%16)-8,route=[8];
    for(let i=1;i<=Math.abs(delta);i++)route.push((8+Math.sign(delta)*i+16)%16);
    for(const i of route)put({...cells[i],ms:i===target?240:85},'reaction');
    for(const i of route.slice(0,-1).reverse())put({...cells[i],ms:85},'reaction');
   }else{
    const s=m.interactions.states[name];
    for(let col=0;col<s.durations_ms.length;col++)put(point(s.row,col,s.durations_ms[col]),'reaction');
    if(['waving','working','waiting','review'].includes(name))for(let col=s.durations_ms.length-2;col>=0;col--)put(point(s.row,col,80),'reaction');
   }
   neutral();
  }
  if(from==='down')for(const col of b.down.start_cols)put(point(b.down.row,col,b.down.frame_ms),'resume');
  else for(const p of m.transitions['down-to-'+from].frames.slice(b.down.stop_cols.length))put(p,'resume');
  return {from,frames,index:0,elapsed:0,names:job.names};
 }
 function advance(n,dt,m){
  if(!m?.interactions)return false;
  if(!n.characterInteraction&&n.interactionRequest&&!n.touristTurn){n.characterInteraction=plan(n,m,n.interactionRequest);n.interactionRequest=null}
  const a=n.characterInteraction;if(!a)return false;
  a.elapsed+=Math.max(0,Number.isFinite(dt)?dt:0)*1000;
  while(a.elapsed>=a.frames[a.index].ms){a.elapsed-=a.frames[a.index].ms;if(++a.index===a.frames.length){n.characterInteraction=null;n.touristFacing=a.from;n.touristRequested=a.from;n.gaitDistance=0;n.spriteRow=m.walks[a.from].row;n.spriteFrame=0;n.spriteFlip=false;return true}}
  const p=a.frames[a.index];n.spriteRow=p.row;n.spriteFrame=p.col;n.spriteFlip=false;return true;
 }
 return Object.freeze({request,plan,advance});
})();
