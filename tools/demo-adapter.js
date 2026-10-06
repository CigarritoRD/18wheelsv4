/* DEMONSTRATION ONLY. No real authentication, no server, no cross-device sync.
   This adapter is included only in the standalone preview, never in the full app. */
window.EW_DEMO=true;
(()=>{
const KEY='18wheelers-jobs-preview-three-roles-v2';
const ROLES=['admin','technician','requester'];
const REQUEST_FIELDS=['title','description','unit','location','category','priority','due_date'];
const iso=()=>new Date().toISOString();
const day=n=>{const d=new Date();d.setDate(d.getDate()+n);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const truckImage=(kind='truck')=>{
 const artwork=kind==='tires'?`<ellipse cx="250" cy="189" rx="175" ry="17" fill="#cbd0d3"/><g fill="#24303a" stroke="#64737e" stroke-width="4"><circle cx="163" cy="123" r="67"/><circle cx="314" cy="123" r="67"/></g><g fill="#8997a1" stroke="#bec7cd" stroke-width="5"><circle cx="163" cy="123" r="30"/><circle cx="314" cy="123" r="30"/></g><g fill="#354451"><circle cx="163" cy="123" r="10"/><circle cx="314" cy="123" r="10"/></g><path d="M121 87l10 8m-13 26h13m-4 34 10-7m179-65 10 8m-50 37h14m53 13 12 6" stroke="#465661" stroke-width="9"/>`:`<ellipse cx="251" cy="181" rx="210" ry="16" fill="#c9d1d7"/><rect x="38" y="49" width="245" height="111" rx="6" fill="#e6e9eb" stroke="#b7c1c8" stroke-width="2"/><path d="M57 56v95M78 56v95M99 56v95M120 56v95M141 56v95M162 56v95M183 56v95M204 56v95M225 56v95M246 56v95M267 56v95" stroke="#ccd3d8" stroke-width="2"/><path d="M288 57h56l38 57h44v52H288z" fill="#364b60"/><path d="M302 70h34l27 41h-61z" fill="#a5c3d5"/><path d="M298 125h112v8H298z" fill="#ee874e"/><path d="M297 143h42M370 153h56" stroke="#8191a0" stroke-width="4"/><rect x="39" y="158" width="392" height="10" rx="3" fill="#5b6875"/><g fill="#2a3640" stroke="#a9b4bd" stroke-width="4"><circle cx="101" cy="169" r="24"/><circle cx="155" cy="169" r="24"/><circle cx="322" cy="169" r="24"/><circle cx="391" cy="169" r="24"/></g><g fill="#a9b7c2"><circle cx="101" cy="169" r="10"/><circle cx="155" cy="169" r="10"/><circle cx="322" cy="169" r="10"/><circle cx="391" cy="169" r="10"/></g>`;
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 240"><defs><linearGradient id="g" x2="0" y2="1"><stop stop-color="#eef1f3"/><stop offset="1" stop-color="#dce2e6"/></linearGradient></defs><rect width="480" height="240" fill="url(#g)"/><path d="M0 184h480" stroke="#c9d2d9"/><path d="M30 205h40m290 0h80" stroke="#c5ced5" stroke-width="2"/>${artwork}<text x="20" y="24" font-family="Arial,sans-serif" font-size="10" letter-spacing="1.5" fill="#7c8d9b">DEMO / ILLUSTRATION</text><rect x="385" y="210" width="75" height="19" rx="4" fill="#f6f8fa"/><text x="422" y="223" text-anchor="middle" font-family="Arial,sans-serif" font-size="9" fill="#94a0aa">SAMPLE IMAGE</text></svg>`;
 return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);
};
function seed(){
 const users=[{id:1,name:'Demo Admin',email:'admin@example.test',role:'admin'},{id:2,name:'Carlos M.',email:'carlos@example.test',role:'technician'},{id:3,name:'Miguel R.',email:'miguel@example.test',role:'technician'},{id:4,name:'Ana L.',email:'ana@example.test',role:'technician'},{id:5,name:'Demo Requester',email:'requester@example.test',role:'requester'},{id:6,name:'Other Requester',email:'other-requester@example.test',role:'requester'}].map(u=>({...u,active:1,must_change:0,created_at:iso()}));
 const rows=[
 [1,'Check trailer marker lights','Trailer #408','Inspection','Normal','New',null,2,'Inspect all side marker lights and document any lights that need replacement.'],
 [2,'Replace left rear brake chamber','Volvo VNR #125','Maintenance','High','Assigned',2,0,'Inspect the reported issue. Follow the approved shop procedure and have a qualified technician perform the repair. Upload a before photo and a photo of the completed work.'],
 [3,'Pre-trip inspection & photos','Kenworth T680 #208','Inspection','Normal','Assigned',3,1,'Complete the approved pre-trip inspection. Document any findings and notify the manager before releasing the unit.'],
 [4,'Diagnose air leak','Cascadia #302','Maintenance','Urgent','In Progress',2,-1,'Find and document the source of the reported air leak. Note the repair performed and have the vehicle checked before it returns to service.'],
 [5,'Pick up empty chassis','Chassis #614','Yard','Normal','In Progress',4,0,'Confirm the chassis number and move the unit to the assigned staging area. Upload a reference photo on arrival.'],
 [6,'Replace worn drive tires','Kenworth T680 #211','Maintenance','High','On Hold',3,2,'Awaiting replacement tires. Record the installed tire information and add photos when the work has been completed.'],
 [7,'Weekly yard safety check','Main yard','Inspection','Normal','Completed',4,-1,'Walk the yard, review the approved safety checklist, and document any concerns for follow-up.'],
 [8,'Service and fluid check','Volvo VNR #119','Maintenance','Low','Completed',2,-2,'Complete the scheduled service using the approved maintenance procedure and record the work performed.']
 ];
 const jobs=rows.map(([id,title,unit,category,priority,status,assignee_id,due,description])=>({id,title,unit,category,priority,status,assignee_id,due_date:day(due),description,location:category==='Yard'?'Main yard / Staging area':'Main yard / Shop',created_by:[1,2,4,8].includes(id)?5:id===3?6:1,created_at:iso(),updated_at:iso(),completed_at:status==='Completed'?iso():null,archived:0,version:1}));
 const photos=[{id:1,job_id:2,url:truckImage(),phase:'Before',caption:'Reference image - demo illustration',uploaded_by:1,created_at:iso(),original_name:'sample-truck.svg'},{id:2,job_id:6,url:truckImage('tires'),phase:'Before',caption:'Reference image - demo illustration',uploaded_by:3,created_at:iso(),original_name:'sample-tires.svg'},{id:3,job_id:8,url:truckImage(),phase:'After',caption:'Completed service - demo illustration',uploaded_by:2,created_at:iso(),original_name:'sample-service.svg'}];
 const activity=jobs.map((j,i)=>({id:i+1,job_id:j.id,user_id:j.created_by,kind:'created',body:'Created this sample job.',created_at:iso()}));
 activity.push({id:9,job_id:4,user_id:2,kind:'comment',body:'Inspection started. I will upload photos of the findings.',created_at:iso()},{id:10,job_id:6,user_id:3,kind:'comment',body:'Waiting for the replacement tires to arrive.',created_at:iso()});
 return {users,jobs,photos,activity,notifications:[{id:1,user_id:1,job_id:4,body:'Carlos M. started: Diagnose air leak',seen:0,created_at:iso()},{id:2,user_id:2,job_id:2,body:'Assigned to you: Replace left rear brake chamber',seen:0,created_at:iso()},{id:3,user_id:5,job_id:4,body:'Your request is In Progress: Diagnose air leak',seen:0,created_at:iso()}],current:1};
}
let store;try{store=JSON.parse(localStorage.getItem(KEY)||'null')||seed();if(!Array.isArray(store.jobs))store=seed();}catch{store=seed();}
function save(){try{localStorage.setItem(KEY,JSON.stringify(store));}catch{throw new Error('This browser cannot save more demo data. Remove some photos, reset the demo, or use the full app for shared storage.');}}
const user=()=>store.users.find(u=>u.id===store.current&&u.active);
const next=items=>Math.max(0,...items.map(x=>x.id))+1;
const clone=value=>JSON.parse(JSON.stringify(value));
function canView(j){return Boolean(j&&user()&&(user().role==='admin'||(user().role==='technician'&&j.assignee_id===user().id)||(user().role==='requester'&&j.created_by===user().id)));}
function getJob(id){const j=store.jobs.find(j=>j.id===id);if(!canView(j))throw new Error('Job not found.');return j;}
function decorate(j){const photos=store.photos.filter(p=>p.job_id===j.id);return {...j,created_by_name:store.users.find(u=>u.id===j.created_by)?.name||'',assignee_name:store.users.find(u=>u.id===j.assignee_id)?.name||'',photo_count:photos.length,comment_count:store.activity.filter(a=>a.job_id===j.id&&a.kind==='comment').length,cover_url:photos[0]?.url||null};}
function log(jid,kind,body){store.activity.push({id:next(store.activity),job_id:jid,user_id:user().id,kind,body,created_at:iso()});}
function notify(recipient,jid,body){if(recipient&&recipient!==user().id)store.notifications.push({id:next(store.notifications),user_id:recipient,job_id:jid,body,seen:0,created_at:iso()});}
function notifyParticipants(j,body){const ids=new Set([...store.users.filter(u=>u.role==='admin'&&u.active).map(u=>u.id),j.created_by,j.assignee_id]);ids.forEach(id=>notify(id,j.id,body));}
function manager(){if(user()?.role!=='admin')throw new Error('Only an admin can do that.');}
function validateJob(j){if(!j.title?.trim())throw new Error('A job title is required.');if(!['New','Assigned','In Progress','On Hold','Completed'].includes(j.status))throw new Error('Invalid job status.');if(!j.assignee_id&&['Assigned','In Progress'].includes(j.status))throw new Error('Assign a technician before starting this job.');if(j.assignee_id&&!store.users.some(u=>u.id===j.assignee_id&&u.active&&u.role==='technician'))throw new Error('Choose an active technician.');}
async function photoData(file){
 if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw new Error('Use JPG, PNG, or WebP photos.');
 const blob=URL.createObjectURL(file);
 try{const img=await new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('Could not read this photo.'));image.src=blob;});const canvas=document.createElement('canvas');const scale=Math.min(1,1400/Math.max(img.width,img.height));canvas.width=Math.round(img.width*scale);canvas.height=Math.round(img.height*scale);const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);return canvas.toDataURL('image/jpeg',.8);}finally{URL.revokeObjectURL(blob);}
}
window.demoApi=async(path,opts={})=>{
 const method=opts.method||'GET',data=opts.body||{},before=clone(store);
 try{
 let result={ok:true};const parts=path.split('?')[0].split('/').filter(Boolean);
 if(path==='/api/session')return {needs_setup:false,user:clone(user()),csrf:'demo-only'};
 if(path==='/api/logout')return {ok:true};
 if(path==='/api/password')throw new Error('The demo does not use real passwords. Password management is available in the full app.');
 if(path==='/api/login')return {user:clone(user()),csrf:'demo-only'};
 if(!user())throw new Error('Select a demo account.');
 if(parts[1]==='users'){
  manager();const id=Number(parts[2]);
  if(method==='GET')return {users:clone(store.users)};
  if(method==='POST'){
   if(!ROLES.includes(data.role))throw new Error('Choose a valid role.');
   if(store.users.some(u=>u.email.toLowerCase()===data.email.toLowerCase()))throw new Error('An account with this email already exists.');
   const item={id:next(store.users),name:data.name,email:data.email,role:data.role,active:1,must_change:0,created_at:iso()};store.users.push(item);result={user:item};
  }else{
   const account=store.users.find(u=>u.id===id);if(!account)throw new Error('Account not found.');
   if('password' in data)throw new Error('No real passwords are stored in the demo. Use the full app to reset passwords.');
   if(data.role&&!ROLES.includes(data.role))throw new Error('Choose a valid role.');
   if(id===user().id&&(data.active===false||(data.role&&data.role!=='admin')))throw new Error('You cannot deactivate or demote your own admin account.');
   if((data.active===false||(data.role&&data.role!==account.role&&data.role!=='technician'))&&store.jobs.some(j=>j.assignee_id===id&&!j.archived&&j.status!=='Completed'))throw new Error('Reassign this account\'s open jobs first.');
   Object.assign(account,data);result={user:account};
  }
 }else if(parts[1]==='jobs'){
  const id=Number(parts[2]);
  if(!id&&method==='GET')return {jobs:clone(store.jobs.filter(j=>Boolean(j.archived)===path.includes('archived=1')&&canView(j)).map(decorate))};
  if(!id&&method==='POST'){
   if(!['admin','requester'].includes(user().role))throw new Error('Only admins and requesters can create jobs.');
   if(user().role==='requester'&&Object.keys(data).some(k=>!REQUEST_FIELDS.includes(k)))throw new Error('Requesters cannot set assignments or status.');
   const clean={title:'',description:'',unit:'',location:'',category:'Maintenance',priority:'Normal',due_date:'',status:data.assignee_id?'Assigned':'New',assignee_id:null,...data};
   if(user().role==='requester'){clean.status='New';clean.assignee_id=null;}
   const j={...clean,id:next(store.jobs),created_by:user().id,created_at:iso(),updated_at:iso(),completed_at:clean.status==='Completed'?iso():null,archived:0,version:1};
   validateJob(j);store.jobs.push(j);log(j.id,'created',user().role==='requester'?'Submitted this request.':'Created this job.');
   if(user().role==='requester')store.users.filter(u=>u.role==='admin'&&u.active).forEach(u=>notify(u.id,j.id,'New request: '+j.title));
   notify(j.assignee_id,j.id,'Assigned to you: '+j.title);result={job:decorate(j)};
  }else{
   const j=getJob(id);
   if(method==='GET')return {job:clone(decorate(j)),photos:clone(store.photos.filter(p=>p.job_id===id).map(p=>({...p,uploaded_by_name:store.users.find(u=>u.id===p.uploaded_by)?.name||''})).reverse()),activity:clone(store.activity.filter(a=>a.job_id===id).map(a=>({...a,user_name:store.users.find(u=>u.id===a.user_id)?.name||''})).reverse())};
   if(parts[3]==='archive'){manager();j.archived=data.archived?1:0;j.version++;log(id,'archived',j.archived?'Archived this job.':'Restored this job.');}
   else if(parts[3]==='comments'){if(j.archived)throw new Error('Restore this job first.');log(id,'comment',data.body);notifyParticipants(j,user().name+' commented on '+j.title);}
   else if(parts[3]==='photos'){
    if(j.archived)throw new Error('Restore this job first.');
    if(user().role==='requester'&&!['Before','General'].includes(data.get('phase')))throw new Error('Requesters can add Before or General photos.');
    const files=data.getAll('files');for(const file of files)store.photos.push({id:next(store.photos),job_id:id,url:await photoData(file),phase:data.get('phase'),caption:data.get('caption'),uploaded_by:user().id,created_at:iso(),original_name:file.name});log(id,'photos','Added '+files.length+' photo(s).');notifyParticipants(j,user().name+' added photos to '+j.title);result={ok:true,count:files.length};
   }else if(method==='PATCH'){
    if(j.archived)throw new Error('Restore this job before editing it.');
    if(user().role==='requester')throw new Error('Requesters cannot change job details or status.');
    if(user().role==='technician'&&data.status&&!['In Progress','On Hold','Completed'].includes(data.status))throw new Error('Technicians can select In Progress, On Hold, or Completed.');
    if(j.version!==data.version)throw new Error('This job changed. Close and reopen it before saving.');
    if(user().role!=='admin'&&Object.keys(data).some(k=>!['status','version'].includes(k)))throw new Error('Only admins can edit job details.');
    const updated={...j,...data};validateJob(updated);
    if(data.status&&data.status!==j.status){log(id,'status','Status changed: '+j.status+' -> '+data.status+'.');updated.completed_at=data.status==='Completed'?iso():null;notifyParticipants({...j,assignee_id:updated.assignee_id},j.title+': '+data.status);}
    if('assignee_id' in data&&data.assignee_id!==j.assignee_id){log(id,'assignment','Assigned to '+(store.users.find(u=>u.id===data.assignee_id)?.name||'no one')+'.');notify(data.assignee_id,id,'Assigned to you: '+j.title);notify(j.created_by,id,j.title+': assignment updated.');}
    Object.assign(j,updated,{version:j.version+1,updated_at:iso()});result={job:decorate(j)};
   }
  }
 }else if(parts[1]==='photos'&&method==='DELETE'){
  manager();const id=Number(parts[2]);const photo=store.photos.find(p=>p.id===id);store.photos=store.photos.filter(p=>p.id!==id);if(photo)log(photo.job_id,'photos','Removed a photo.');
 }else if(parts[1]==='notifications'){
  if(method==='GET')return {notifications:clone(store.notifications.filter(n=>n.user_id===user().id&&canView(store.jobs.find(j=>j.id===n.job_id))).reverse())};store.notifications.filter(n=>n.user_id===user().id).forEach(n=>n.seen=1);
 }else throw new Error('This feature is available in the full app.');
 if(method!=='GET')save();return clone(result);
 }catch(error){store=before;throw error;}
};
window.demoSwitch=role=>{const account=store.users.find(u=>u.role===role&&u.active);if(!account)throw new Error('No active demo account for this role.');store.current=account.id;save();};
window.demoReset=()=>{store=seed();save();};
window.demoExport=()=>{
 manager();
 const columns=['id','title','unit','status','priority','assignee_name','due_date','photo_count'];
 const csv=columns.join(',')+'\r\n'+store.jobs.map(decorate).map(j=>columns.map(k=>{let v=String(j[k]??'');if(/^[\s]*[=+\-@]/.test(v))v="'"+v;return '"'+v.replaceAll('"','""')+'"';}).join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='18wheelers-demo-jobs.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);
};
})();
