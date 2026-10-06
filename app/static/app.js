/* 18wheelers Jobs - dependency-free, responsive browser interface.
   Demo builds inject a separate, explicitly labeled local-only API adapter. */
'use strict';
const ICONS={
 grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
 board:'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18M15 3v18M5.5 7h1M11.5 7h1M17.5 7h1"/>',
 check:'<path d="m5 12 4 4L19 6"/>',
 checkCircle:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
 clipboard:'<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 11h6M9 15h4"/>',
 users:'<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 4v2"/>',
 archive:'<rect x="3" y="3" width="18" height="5" rx="1"/><path d="M5 8v12h14V8M10 12h4"/>',
 help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1.5 1-1.5 1-1.5 3M12 17h.01"/>',
 logout:'<path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
 bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
 chevron:'<path d="m9 5 7 7-7 7"/>',
 arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 alert:'<path d="m12 3 10 18H2L12 3zM12 9v5M12 17h.01"/>',
 truck:'<path d="M3 5h11v12H3zM14 10h4l3 4v3h-7M3 17H1"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
 camera:'<path d="m8 5 2-2h4l2 2h5v15H3V5h5z"/><circle cx="12" cy="12" r="4"/>',
 comment:'<path d="M21 15a3 3 0 0 1-3 3H8l-5 3V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3z"/>',
 flag:'<path d="M5 21V3m0 1c5-4 9 4 14 0v10c-5 4-9-4-14 0"/>',
 list:'<path d="M9 6h12M9 12h12M9 18h12M3 6h.01M3 12h.01M3 18h.01"/>',
 download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
 upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
 close:'<path d="m6 6 12 12M6 18 18 6"/>',
 edit:'<path d="m16 3 5 5-12 12H4v-5L16 3zM13 6l5 5"/>',
 trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
 lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
 menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
 refresh:'<path d="M20 11a8 8 0 0 0-14-5L3 9m0-6v6h6M4 13a8 8 0 0 0 14 5l3-3m0 6v-6h-6"/>',
 wrench:'<path d="M14 6a5 5 0 0 0-6 6L2 18l4 4 6-6a5 5 0 0 0 6-6l-4 4-4-4 4-4z"/>',
 location:'<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0z"/><circle cx="12" cy="10" r="2"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h2M15 14h2"/>',
 shield:'<path d="m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6l9-4z"/><path d="m8 12 3 3 5-6"/>'
};
const icon=(name,cls='')=>`<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]||ICONS.clipboard}</svg>`;
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const STATUSES=['New','Assigned','In Progress','On Hold','Completed'];
const PRIORITIES=['Low','Normal','High','Urgent'];
const CATEGORIES=['Maintenance','Inspection','Delivery','Yard','Office','Other'];
const DEMO=Boolean(window.EW_DEMO);
const S={user:null,csrf:'',jobs:[],users:[],notifications:[],page:'overview',view:'board',search:'',assignee:'',priority:'',status:'',detail:null,detailTab:'photos',modal:null,needsSetup:false};
const root=document.getElementById('app');
const overlayRoot=document.getElementById('overlay-root');
let focusBeforeModal=null;
const isAdmin=()=>S.user?.role==='admin';
const isTechnician=()=>S.user?.role==='technician';
const isRequester=()=>S.user?.role==='requester';
const canCreate=()=>isAdmin()||isRequester();
const roleLabel=role=>({admin:'Admin',technician:'Technician',requester:'Requester'}[role]||'Unknown');
const roleSummary=()=>isAdmin()?'Admin: all jobs, assignments, and accounts.':isTechnician()?'Technician: only your assigned jobs.':'Requester: only requests you submitted.';
const editableStatuses=current=>isAdmin()?STATUSES:[...new Set([current,'In Progress','On Hold','Completed'])];
const localDate=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const initials=name=>String(name||'?').trim().split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
const avatar=(name,id=0)=>`<span class="avatar ${['','warm','violet','green'][Number(id)%4]}" title="${esc(name||'Unassigned')}">${esc(initials(name))}</span>`;
const jobCode=id=>`JOB-${String(id).padStart(4,'0')}`;
const statusBadge=status=>`<span class="status-badge ${esc(status.replaceAll(' ','-'))}"><i class="dot"></i>${esc(status)}</span>`;
const priorityBadge=priority=>`<span class="priority ${esc(priority)}">${icon('flag')}${esc(priority)}</span>`;
const longDate=value=>value?new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit'}):'No date';
const dueDate=value=>value?new Date(value+'T12:00:00').toLocaleDateString(undefined,{month:'short',day:'numeric'}):'No due date';
const overdue=job=>Boolean(job.due_date&&job.due_date<localDate()&&job.status!=='Completed');
const options=(values,selected)=>values.map(x=>`<option value="${esc(x)}" ${x===selected?'selected':''}>${esc(x)}</option>`).join('');
function assigneeOptions(selected,empty='Unassigned'){
 return `<option value="">${esc(empty)}</option>`+S.users.filter(u=>u.active&&u.role==='technician').map(u=>`<option value="${u.id}" ${String(u.id)===String(selected)?'selected':''}>${esc(u.name)}</option>`).join('');
}
function toast(message,error=false){
 const el=document.createElement('div');el.className='toast'+(error?' error':'');el.textContent=message;
 document.getElementById('toast-root').replaceChildren(el);setTimeout(()=>el.remove(),6500);
}
async function api(path,opts={}){
 if(DEMO)return window.demoApi(path,opts);
 const method=opts.method||'GET';const headers={'Accept':'application/json'};
 if(!['GET','HEAD'].includes(method))headers['X-CSRF-Token']=S.csrf;
 let body=opts.body;
 if(body!==undefined&&!(body instanceof FormData)){headers['Content-Type']='application/json';body=JSON.stringify(body);}
 const response=await fetch(path,{method,headers,body,credentials:'same-origin'});
 let result;try{result=await response.json();}catch{result={error:'The server returned an unexpected response.'};}
 if(!response.ok){const error=new Error(result.error||'Request failed.');error.status=response.status;throw error;}
 return result;
}
async function run(action){
 try{await action();}catch(error){
  if(error.status===401&&S.user){S.user=null;closeModal();await init();}
  toast(error.message||'Something went wrong.',true);
 }
}
async function refresh(renderPage=true){
 const [jobs,users,notifs]=await Promise.all([
  api('/api/jobs'+(S.page==='archive'?'?archived=1':'')),
  isAdmin()?api('/api/users'):Promise.resolve({users:[S.user]}),
  api('/api/notifications')
 ]);
 S.jobs=jobs.jobs;S.users=users.users;S.notifications=notifs.notifications;
 if(renderPage)render();
}
async function init(){
 try{
  const info=await api('/api/session');S.user=info.user;S.csrf=info.csrf;S.needsSetup=info.needs_setup;
  if(!S.user){renderAuth();return;}
  if(S.user.must_change){renderAuth('password');return;}
  if(!isAdmin()&&S.page==='team')S.page='overview';
  await refresh();
 }catch(error){root.innerHTML=`<div class="boot">${icon('alert','big')}<h2>Cannot open the workspace</h2><p>${esc(error.message)}</p><button class="btn primary" data-action="retry">Try again</button></div>`;}
}
function renderAuth(mode){
 const setup=S.needsSetup&&!mode;const password=mode==='password';
 const setupToken=new URL(location.href).searchParams.get('setup_token')||'';
 root.innerHTML=`<div class="auth-page"><section class="auth-brand-panel"><div class="brand"><span class="brand-mark">18</span><div class="brand-name">18wheelers<small>OPERATIONS WORKSPACE</small></div></div><div class="auth-message"><div class="eyebrow">Built for the people who move it all</div><h1>Good work.<br>Clear ownership.</h1><p>Keep every assignment, update, and job photo in one place. Less back-and-forth. More getting it done.</p><div class="auth-points"><span>${icon('checkCircle')} Assign jobs to your team</span><span>${icon('camera')} Document work with photos</span><span>${icon('board')} See every job from start to finish</span></div></div><p class="auth-copyright">18wheelers &nbsp; / &nbsp; Job management</p></section><section class="auth-form-panel"><form class="auth-form" data-form="${password?'password':setup?'setup':'login'}"><div class="eyebrow">${password?'Make it yours':setup?'Welcome to your workspace':'Welcome back'}</div><h2>${password?'Set your own password':setup?'Let\'s get you set up.':'Sign in to 18wheelers.'}</h2><p class="subtitle">${password?'Your admin created a temporary password. Replace it with a private password before opening your jobs.':setup?'Create the first admin account. Then invite your team and start assigning jobs.':'Your jobs, team, and progress. All in one place.'}</p><div class="form-error" role="alert"></div>${setup?`<label class="field"><span class="label">Your name</span><input name="name" required maxlength="100" autocomplete="name" placeholder="Full name"></label>`:''}${!password?`<label class="field"><span class="label">Email address</span><input name="email" type="email" required maxlength="254" autocomplete="username" placeholder="you@yourcompany.com"></label><label class="field"><span class="label">${setup?'Create a password':'Password'}</span><input name="password" type="password" required ${setup?'minlength="12"':''} maxlength="128" autocomplete="${setup?'new-password':'current-password'}" placeholder="${setup?'At least 12 characters':'Enter your password'}"></label>`:`<label class="field"><span class="label">Temporary / current password</span><input name="current_password" type="password" required maxlength="128" autocomplete="current-password"></label><label class="field"><span class="label">New password</span><input name="new_password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"><small>Use at least 12 characters.</small></label><label class="field"><span class="label">Confirm new password</span><input name="confirm_password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label>`}${setup?`<label class="field" ${setupToken?'hidden':''}><span class="label">Server setup token</span><input name="setup_token" value="${esc(setupToken)}" required autocomplete="off"><small>Use the setup link displayed in your server window.</small></label>`:''}<button class="btn primary full" type="submit">${password?'Save my password':setup?'Create my workspace':'Sign in'}${icon('arrow')}</button><p class="auth-foot">${setup?'You choose your own password. No default accounts are created.':password?'Changing your password signs out your other sessions.':'Need access or a password reset? Contact your workspace admin.'}</p>${password?'<button type="button" class="btn quiet full" data-action="logout">Sign out</button>':''}</form></section></div>`;
}
function render(){
 if(!S.user)return renderAuth();
 const admin=isAdmin(),requester=isRequester();
 const names={overview:'Overview',board:'Job board',mine:requester?'My requests':'My jobs',team:'Team',archive:admin?'Archive':'History'};
 const nav=[['overview','grid','Overview'],...(admin?[['board','board','Job board'],['team','users','Team']]:[['mine','clipboard',names.mine]]),['archive','archive',names.archive]];
 const unread=S.notifications.filter(n=>!n.seen).length;
 const open=S.jobs.filter(j=>j.status!=='Completed').length;
 root.innerHTML=`<div class="shell"><aside class="sidebar" id="sidebar"><div class="brand"><span class="brand-mark">18</span><div class="brand-name">18wheelers<small>OPERATIONS</small></div></div><div class="nav-caption">${esc(roleLabel(S.user.role))} WORKSPACE</div>${nav.map(([id,ic,name])=>`<button class="nav-link ${S.page===id?'active':''}" data-action="nav" data-page="${id}">${icon(ic)}${name}${id==='board'&&open?`<span class="count">${open}</span>`:''}</button>`).join('')}<div class="sidebar-spacer"></div><div class="workspace-card"><div class="mini">18W WORKSPACE</div><strong><i class="dot green"></i>${DEMO?'Local demonstration':'Connected to server'}</strong></div><button class="nav-link" data-action="help">${icon('help')}Help & setup</button><button class="nav-link" data-action="password">${icon('lock')}Change password</button><div class="account">${avatar(S.user.name,S.user.id)}<div><div class="account-name">${esc(S.user.name)}</div><small>${roleLabel(S.user.role)}</small></div><button class="icon-btn" data-action="logout" title="Sign out" aria-label="Sign out">${icon('logout')}</button></div></aside><main class="main">${DEMO?`<div class="demo-banner"><strong>INTERACTIVE DEMO</strong><span>Local sample data only. Try a role:</span><div class="demo-role-switch" aria-label="Demo role">${['admin','technician','requester'].map(role=>`<button data-action="demo-switch" data-role="${role}" class="${S.user.role===role?'active':''}" aria-pressed="${S.user.role===role}">${roleLabel(role)}</button>`).join('')}</div><button data-action="demo-reset">Reset demo</button></div>`:''}<header class="topbar"><button class="icon-btn mobile-toggle" aria-label="Open navigation" data-action="menu">${icon('menu')}</button><div class="breadcrumb"><span>Workspace</span>${icon('chevron')}<strong>${names[S.page]}</strong></div><div class="top-actions"><span class="top-date">${new Date().toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric',year:'numeric'})}</span><button class="icon-btn" data-action="notifications" title="Notifications" aria-label="Notifications${unread?', unread':''}">${icon('bell')}${unread?'<i class="notif-dot"></i>':''}</button>${avatar(S.user.name,S.user.id)}</div></header><div class="content">${S.page==='team'?teamPage():jobsPage()}</div></main></div>`;
}
function metrics(){
 const jobs=S.jobs;const open=jobs.filter(j=>j.status!=='Completed').length;const progress=jobs.filter(j=>j.status==='In Progress').length;const done=jobs.filter(j=>j.status==='Completed').length;const late=jobs.filter(overdue).length;
 return `<section class="metrics" aria-label="Job statistics">${[['Open jobs',open,'clipboard','Waiting, assigned, or underway'],['In progress',progress,'clock','Work happening right now'],['Completed',done,'checkCircle','Finished and documented'],['Overdue',late,'alert','Past due and still open']].map(([label,value,ic,note])=>`<div class="metric"><div class="metric-top">${label}<span class="metric-icon">${icon(ic)}</span></div><div class="metric-value">${value.toString().padStart(2,'0')}</div><div class="metric-bottom">${note}</div></div>`).join('')}</section>`;
}
function jobsPage(){
 const history=S.page==='archive';
 const heading=history?'Finished here. Never lost.':isRequester()?'Report it. Track it.':isTechnician()?'Your work, in focus.':S.page==='board'?'A clear view of every job.':'Keep the fleet moving.';
 const sub=history?'Archived jobs, photos, and updates. Read-only history.':isRequester()?'Describe what needs attention. Your admin assigns it. Follow every update.':isTechnician()?'See your assignments, document your work, and keep everyone updated.':'Review requests, assign technicians, and follow each job through completion.';
 return `<section class="page-heading"><div><div class="eyebrow">${esc(roleLabel(S.user.role))} / ${history?'Job history':'Daily operations'}</div><h1>${heading}</h1><p class="subtitle">${sub}</p></div><div class="actions">${isAdmin()?`<button class="btn" data-action="export">${icon('download')}Export</button>`:''}${canCreate()&&!history?`<button class="btn primary" data-action="new-job">${icon('plus')}${isRequester()?'New request':'New job'}</button>`:''}</div></section>${S.page==='overview'?metrics():''}<section><div class="section-head"><div><h2>${history?'Archived jobs':isRequester()?'Your requests':isTechnician()?'Assigned to you':'Work board'}</h2><div class="section-note">${history?(isAdmin()?'Restore a job to put it back on the work board.':'Only your permitted job history is shown.'):'Open a job to see instructions, photos, and updates.'}</div></div><span class="live-pill"><i class="dot green"></i>${DEMO?'Demo workspace':'Updates every 30 seconds'}</span></div><div class="filters"><label class="search-box">${icon('search')}<input id="job-search" type="search" placeholder="Search jobs, truck numbers..." aria-label="Search jobs" value="${esc(S.search)}"></label>${isAdmin()?`<select class="filter-select" id="filter-assignee" aria-label="Filter by assignee">${assigneeOptions(S.assignee,'All technicians')}</select>`:''}<select class="filter-select" id="filter-priority" aria-label="Filter by priority"><option value="">All priorities</option>${options(PRIORITIES,S.priority)}</select><select class="filter-select" id="filter-status" aria-label="Filter by status"><option value="">All statuses</option>${options(STATUSES,S.status)}</select><div class="view-switch" aria-label="Job view"><button class="${S.view==='board'?'active':''}" data-action="view" data-view="board">${icon('board')}Board</button><button class="${S.view==='list'?'active':''}" data-action="view" data-view="list">${icon('list')}List</button></div></div><div id="jobs-view">${jobsView()}</div></section><footer class="bottom-note"><span>${icon('shield')}${roleSummary()}</span><span>${DEMO?'Local demo only. No company records used.':'Photos and updates are shared with the admin and the people on this job.'}</span></footer>`;
}
function filteredJobs(){
 const q=S.search.toLowerCase();return S.jobs.filter(j=>(S.page!=='mine'||(isRequester()?j.created_by===S.user.id:j.assignee_id===S.user.id))&&(!S.assignee||String(j.assignee_id)===S.assignee)&&(!S.priority||j.priority===S.priority)&&(!S.status||j.status===S.status)&&(!q||[j.title,j.unit,j.description,j.assignee_name,j.location,jobCode(j.id)].join(' ').toLowerCase().includes(q))).sort((a,b)=>PRIORITIES.indexOf(b.priority)-PRIORITIES.indexOf(a.priority)||(a.due_date||'9999').localeCompare(b.due_date||'9999'));
}
function emptyState(title,description,button=''){
 return `<div class="empty-state"><div class="empty-icon">${icon('clipboard','big')}</div><h3>${esc(title)}</h3><p>${esc(description)}</p>${button}</div>`;
}
function jobsView(){
 const jobs=filteredJobs();
 if(!jobs.length)return emptyState(S.jobs.length?'No matching jobs':S.page==='archive'?'Your archive is empty':'A clear board. A fresh start.',S.jobs.length?'Try another search or clear your filters.':isAdmin()?'Add your team, then create your first job and attach any reference photos.':isRequester()?'Submit a request with a description and photos. Your admin will assign a technician.':'Your admin has not assigned any jobs to you yet.',canCreate()&&!S.jobs.length&&S.page!=='archive'?'<button class="btn primary" data-action="new-job">'+icon('plus')+(isRequester()?'Submit a request':'Create a job')+'</button>':'');
 if(S.view==='list'||S.page==='archive')return `<div class="table-wrap"><table><thead><tr><th>JOB</th><th>ASSIGNED TO</th><th>STATUS</th><th>PRIORITY</th><th>DUE</th><th>PHOTOS</th></tr></thead><tbody>${jobs.map(j=>`<tr class="job-row" data-action="open-job" data-id="${j.id}" tabindex="0" role="button" aria-label="Open ${esc(j.title)}"><td class="table-title">${esc(j.title)}<small>${jobCode(j.id)} &nbsp; ${esc(j.unit||'No unit')}</small></td><td><div class="person-inline">${avatar(j.assignee_name,j.assignee_id)}${esc(j.assignee_name||'Unassigned')}</div></td><td>${statusBadge(j.status)}</td><td>${priorityBadge(j.priority)}</td><td><span class="due-label ${overdue(j)?'overdue':''}">${dueDate(j.due_date)}</span></td><td>${j.photo_count||0}</td></tr>`).join('')}</tbody></table></div>`;
 return `<div class="board">${STATUSES.filter(s=>!S.status||s===S.status).map(status=>{const items=jobs.filter(j=>j.status===status);return `<section class="column" data-status="${status}"><div class="column-head"><i class="dot"></i>${status}<span class="column-count">${items.length}</span>${isAdmin()?`<button class="icon-btn" data-action="new-job" data-status="${status}" aria-label="New ${status} job">${icon('plus')}</button>`:''}</div>${items.length?items.map(jobCard).join(''):'<div class="empty-column">Nothing here yet.<br>A little breathing room.</div>'}${isAdmin()?`<button class="add-card" data-action="new-job" data-status="${status}">${icon('plus')}Add job</button>`:''}</section>`;}).join('')}</div>`;
}
function jobCard(job){
 return `<button class="job-card" data-action="open-job" data-id="${job.id}"><div class="job-card-top"><span class="job-code">${jobCode(job.id)}</span>${priorityBadge(job.priority)}</div><h3 class="job-title">${esc(job.title)}</h3><div class="unit-line">${icon('truck')}${esc(job.unit||'No truck / unit')}</div>${job.cover_url?`<img class="job-image" src="${esc(job.cover_url)}" alt="Job reference photo" loading="lazy">`:''}<span class="category-tag ${esc(job.category)}">${esc(job.category)}</span><div class="job-card-footer">${avatar(job.assignee_name,job.assignee_id)}<span class="due-label ${overdue(job)?'overdue':''}">${dueDate(job.due_date)}</span><div class="job-meta"><span>${icon('camera')}${job.photo_count||0}</span><span>${icon('comment')}${job.comment_count||0}</span></div></div></button>`;
}
function teamPage(){
 return `<section class="page-heading"><div><div class="eyebrow">The people behind the work</div><h1>Your team. In sync.</h1><p class="subtitle">Manage access and see who has work on their plate.</p></div><button class="btn primary" data-action="new-user">${icon('plus')}Add team member</button></section><div class="section-head"><h2>Team members</h2><span class="team-members-summary">${S.users.filter(u=>u.active).length} active members</span></div><div class="team-grid">${S.users.map(u=>{const jobs=S.jobs.filter(j=>u.role==='requester'?j.created_by===u.id:j.assignee_id===u.id);return `<article class="team-card"><div class="team-card-head">${avatar(u.name,u.id)}<div><h3>${esc(u.name)}</h3><p>${esc(u.email)}</p></div></div><span class="role-pill">${roleLabel(u.role)}${!u.active?' / Deactivated':u.must_change?' / First login pending':''}</span><div class="team-stats"><span><strong>${jobs.filter(j=>j.status!=='Completed').length}</strong> open jobs</span><span><strong>${jobs.filter(j=>j.status==='Completed').length}</strong> completed</span></div><div class="actions"><button class="btn small" data-action="edit-user" data-id="${u.id}">${icon('edit')}Edit</button>${u.id!==S.user.id?`<button class="btn small quiet" data-action="reset-password" data-id="${u.id}">Reset password</button>`:''}</div></article>`;}).join('')}</div><p class="hint">Admins manage all jobs and accounts. Technicians see only assigned work. Requesters see only their submitted requests. Accounts use email as a sign-in name; invitations are not emailed automatically.</p>`;
}
function modal(title,subtitle,body,footer='',wide=false,kind='generic'){
 if(!S.modal)focusBeforeModal=document.activeElement;
 S.modal=kind;
 overlayRoot.innerHTML=`<div class="overlay"><section class="modal ${wide?'wide':''}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-head"><div><h2 id="modal-title">${esc(title)}</h2>${subtitle?`<p>${esc(subtitle)}</p>`:''}</div><button class="icon-btn" data-action="close-modal" aria-label="Close">${icon('close')}</button></header><div class="modal-body">${body}</div>${footer?`<footer class="modal-footer">${footer}</footer>`:''}</section></div>`;
 document.body.style.overflow='hidden';
 requestAnimationFrame(()=>{const focus=overlayRoot.querySelector('input:not([type=file]),textarea,select,button');focus?.focus({preventScroll:true});});
}
function closeModal(){S.modal=null;overlayRoot.innerHTML='';document.body.style.overflow='';focusBeforeModal?.focus?.({preventScroll:true});}
function fileField(id='job-files'){
 return `<label class="upload-box" for="${id}">${icon('upload')}<strong>Add photos or take a picture</strong><small>JPG, PNG, WebP. Up to 8 photos per batch.<br>12 MB per photo; 30 MB per batch. HEIC must be converted.</small><input type="file" id="${id}" name="files" accept="image/jpeg,image/png,image/webp" multiple><div class="file-summary"></div></label>`;
}
function jobForm(job=null,status='New'){
 const editing=Boolean(job),requester=isRequester();
 if(!canCreate()||(editing&&!isAdmin()))throw new Error('Only an admin can edit job details.');
 job=job||{title:'',description:'',unit:'',location:'',category:'Maintenance',priority:'Normal',status,assignee_id:'',due_date:''};
 modal(editing?'Edit job':requester?'Submit a request':'Create a new job',editing?jobCode(job.id):requester?'Describe the issue. An admin will review and assign a technician.':'Clear instructions. The right technician. Everything they need.',`
 <form data-form="job" id="job-form" data-id="${job.id||''}" data-version="${job.version||''}"><div class="form-error" role="alert"></div><div class="form-grid">
 <label class="field full"><span class="label">${requester?'Request':'Job'} title *</span><input name="title" required maxlength="160" value="${esc(job.title)}" placeholder="e.g. Left chassis light is not working"></label>
 <label class="field"><span class="label">Truck / unit number</span><input name="unit" maxlength="80" value="${esc(job.unit)}" placeholder="e.g. Chassis #614"></label>
 <label class="field"><span class="label">Category</span><select name="category">${options(CATEGORIES,job.category)}</select></label>
 ${!requester?`<label class="field"><span class="label">Assigned technician</span><select name="assignee_id">${assigneeOptions(job.assignee_id)}</select></label>`:''}
 <label class="field"><span class="label">${requester?'Requested due date':'Due date'}</span><input name="due_date" type="date" value="${esc(job.due_date)}"></label>
 <label class="field"><span class="label">${requester?'Requested priority':'Priority'}</span><select name="priority">${options(PRIORITIES,job.priority)}</select></label>
 ${!requester?`<label class="field"><span class="label">Status</span><select name="status">${options(STATUSES,job.status)}</select></label>`:''}
 <label class="field full"><span class="label">Location</span><input name="location" maxlength="200" value="${esc(job.location)}" placeholder="e.g. Main yard / Bay 2"></label>
 <label class="field full"><span class="label">${requester?'Describe the issue':'Instructions'}</span><textarea name="description" maxlength="10000" placeholder="Describe what needs attention and add any useful details.">${esc(job.description)}</textarea></label>
 ${editing?'':`<div class="field full"><span class="label">Reference / before photos</span>${fileField()}</div>`}</div>
 ${requester?'<p class="hint">This request starts as New and unassigned. The admin controls the assignment, final priority, and due date. Add corrections as comments after submitting.</p>':''}
 </form>`,`<button class="btn" data-action="${editing?'back-job':'close-modal'}">Cancel</button><button class="btn primary" type="submit" form="job-form">${editing?'Save changes':requester?'Submit request':'Create job'}${icon('arrow')}</button>`,false,'job-form');
}
async function openJob(id,tab='photos'){
 const detail=await api('/api/jobs/'+id);S.detail=detail;S.detailTab=tab;renderDetail();
}
function renderDetail(){
 const {job,photos,activity}=S.detail;const archived=Boolean(job.archived);
 const body=`<div class="detail-header"><span class="job-code">${jobCode(job.id)}</span>${statusBadge(job.status)}${priorityBadge(job.priority)}${archived?'<span class="role-pill">Archived</span>':''}</div><h3 class="detail-title">${esc(job.title)}</h3><div class="unit-line">${icon('truck')}${esc(job.unit||'No truck / unit specified')} &nbsp; / &nbsp; ${esc(job.category)}</div><div class="detail-layout"><section class="detail-main"><p class="description" style="margin-top:21px">${esc(job.description||'No instructions have been added.')}</p><div class="tabs"><button class="${S.detailTab==='photos'?'active':''}" data-action="detail-tab" data-tab="photos">Photos (${photos.length})</button><button class="${S.detailTab==='activity'?'active':''}" data-action="detail-tab" data-tab="activity">Updates & activity (${activity.length})</button></div>${S.detailTab==='photos'?`<div class="actions" style="margin-bottom:18px">${!archived?`<button class="btn small" data-action="upload-photos">${icon('camera')}Add photos</button>`:''}<span class="section-note">Before, after, and reference photos</span></div>${photos.length?`<div class="photo-grid">${photos.map(p=>`<article class="photo-card"><a href="${esc(p.url)}" data-action="lightbox" data-id="${p.id}" aria-label="View ${esc(p.phase)} photo"><img src="${esc(p.url)}" alt="${esc(p.caption||p.phase+' photo')}" loading="lazy"></a><div class="photo-caption"><div><strong>${esc(p.phase)}${p.caption?' / '+esc(p.caption):''}</strong><small>${esc(p.uploaded_by_name)}<br>${longDate(p.created_at)}</small></div>${isAdmin()&&!archived?`<button class="icon-btn" data-action="delete-photo" data-id="${p.id}" title="Delete photo" aria-label="Delete photo">${icon('trash')}</button>`:''}</div></article>`).join('')}</div>`:'<p class="hint">No photos yet. Add a reference image, document the issue, or show the finished work.</p>'}`:`<div class="timeline">${activity.map(a=>`<div class="timeline-item ${esc(a.kind)}"><span class="timeline-icon">${icon(a.kind==='comment'?'comment':a.kind==='photos'?'camera':a.kind==='status'?'refresh':'clipboard')}</span><div class="timeline-body"><strong>${esc(a.user_name)}</strong><time>${longDate(a.created_at)}</time><p>${esc(a.body)}</p></div></div>`).join('')}</div>`}${!archived?`<form class="comment-form" data-form="comment"><textarea name="body" aria-label="Add an update" required maxlength="5000" placeholder="Add an update or a note for the team..."></textarea><button class="btn primary" type="submit">Send${icon('arrow')}</button></form>`:''}</section><aside class="detail-sidebar"><label class="field"><span class="label">Job status</span><select id="detail-status" ${archived||isRequester()?'disabled':''}>${options(editableStatuses(job.status),job.status)}</select>${isRequester()?'<small class="section-note">Only the admin or assigned technician can update status.</small>':''}</label><div class="field"><span class="label">Assigned to</span><div class="person-inline">${avatar(job.assignee_name,job.assignee_id)}<span style="font-size:12px">${esc(job.assignee_name||'Unassigned')}</span></div></div><dl class="detail-info"><div><dt>SUBMITTED BY</dt><dd>${esc(job.created_by_name||'Not specified')}</dd></div><div><dt>DUE DATE</dt><dd class="${overdue(job)?'due-label overdue':''}">${dueDate(job.due_date)}${overdue(job)?' / Overdue':''}</dd></div><div><dt>LOCATION</dt><dd>${esc(job.location||'Not specified')}</dd></div><div class="detail-meta"><dt>CREATED</dt><dd>${longDate(job.created_at)}</dd></div><div class="detail-meta"><dt>LAST EDITED</dt><dd>${longDate(job.updated_at)}</dd></div>${job.completed_at?`<div><dt>COMPLETED</dt><dd>${longDate(job.completed_at)}</dd></div>`:''}</dl>${isAdmin()?`<div class="actions" style="margin-top:20px">${archived?`<button class="btn small full" data-action="archive-job" data-archived="false">${icon('refresh')}Restore job</button>`:`<button class="btn small full" data-action="edit-job">${icon('edit')}Edit job details</button><button class="btn small quiet full" data-action="archive-job" data-archived="true">${icon('archive')}Archive job</button>`}</div>`:''}</aside></div>`;
 modal('Job details','Instructions, photos, and the full story of the work.',body,'',true,'detail');
}
function userForm(account=null){
 const editing=Boolean(account);account=account||{name:'',email:'',role:'requester',active:true};
 modal(editing?'Edit team member':'Add a team member',editing?'Manage this account\'s role and access.':'Choose Admin, Technician, or Requester access.',`<form data-form="user" id="user-form" data-id="${account.id||''}"><div class="form-error" role="alert"></div><div class="form-grid"><label class="field full"><span class="label">Full name *</span><input name="name" value="${esc(account.name)}" required maxlength="100" autocomplete="off"></label><label class="field full"><span class="label">Email / sign-in name *</span><input name="email" type="email" value="${esc(account.email)}" required maxlength="254" autocomplete="off"></label><label class="field"><span class="label">Role</span><select name="role" ${account.id===S.user.id?'disabled':''}>${['admin','technician','requester'].map(role=>`<option value="${role}" ${account.role===role?'selected':''}>${roleLabel(role)}</option>`).join('')}</select></label>${editing?`<label class="field"><span class="label">Account status</span><select name="active" ${account.id===S.user.id?'disabled':''}><option value="true" ${account.active?'selected':''}>Active</option><option value="false" ${!account.active?'selected':''}>Deactivated</option></select></label>`:''}${!editing?`<label class="field full"><span class="label">Temporary password *</span><input name="password" type="password" minlength="12" maxlength="128" required autocomplete="new-password"><small>At least 12 characters. Share this privately. The account holder must change it on first login.</small></label>`:''}</div><p class="hint">Admins manage everything. Technicians work on assigned jobs. Requesters submit and track only their own requests. This app does not send invitation emails.</p></form>`,`<button class="btn" data-action="close-modal">Cancel</button><button class="btn primary" form="user-form" type="submit">${editing?'Save changes':'Create account'}</button>`,false,'user-form');
}
function passwordModal(){
 modal('Change your password','Use a private password with at least 12 characters.',`<form data-form="password" id="password-form"><div class="form-error" role="alert"></div><div class="form-grid"><label class="field full"><span class="label">Current password</span><input name="current_password" type="password" required maxlength="128" autocomplete="current-password"></label><label class="field full"><span class="label">New password</span><input name="new_password" type="password" minlength="12" maxlength="128" required autocomplete="new-password"></label><label class="field full"><span class="label">Confirm new password</span><input name="confirm_password" type="password" minlength="12" maxlength="128" required autocomplete="new-password"></label></div></form>`,`<button class="btn" data-action="close-modal">Cancel</button><button class="btn primary" form="password-form" type="submit">Save password</button>`,false,'password');
}
function help(){
 modal('Three roles. One clear workflow.','18wheelers / Jobs workspace',`<div class="help-content">${DEMO?'<div class="inset-note">This is a local demonstration, not the shared app. All three role views use this browser only. Do not enter real passwords or sensitive company information.</div>':''}<h3>1. Admin</h3><p>Create accounts in Team and choose a role for each person. Review all requests, assign an active technician, set priority and due date, and manage the full job history. Share temporary passwords privately; the app does not send invitation emails.</p><h3>2. Technician</h3><p>See only jobs assigned to you. Set In Progress, On Hold, or Completed, upload before-and-after photos, and add comments. You cannot create accounts, assign work, or edit job details.</p><h3>3. Requester</h3><p>Use New request to report an issue and add reference photos. Requests start New and unassigned. Track only your own requests, read updates, add Before or General photos, and comment. You cannot assign a technician or change job status.</p><h3>Photos and history</h3><p>Use JPG, PNG, or WebP; convert HEIC first. Comments and photos are shared with everyone authorized for the job; there is no private internal-notes area. Archived jobs remain available as read-only History to the assigned technician and original requester. Admins can restore them.</p><h3>Shared team access</h3><p>The full application needs a running server. Follow the included setup and deployment guide. The preview is not a hosted website. Notifications appear inside the app, not through email or text.</p></div>`,`<button class="btn primary" data-action="close-modal">Close</button>`,false,'help');
}
async function submitForm(form){
 const type=form.dataset.form;const data=Object.fromEntries(new FormData(form).entries());
 const errorBox=form.querySelector('.form-error');if(errorBox)errorBox.textContent='';
 const buttons=[...document.querySelectorAll(`button[form="${form.id}"]`),...form.querySelectorAll('button[type="submit"]')];buttons.forEach(b=>b.disabled=true);
 try{
  if(['setup','login'].includes(type)){
   const result=await api('/api/'+type,{method:'POST',body:data});S.user=result.user;S.csrf=result.csrf;S.needsSetup=false;
   if(type==='setup'&&!DEMO)history.replaceState(null,'',location.pathname);
   if(S.user.must_change)renderAuth('password');else await refresh();
  }else if(type==='password'){
   if(data.new_password!==data.confirm_password)throw new Error('The new passwords do not match.');
   const result=await api('/api/password',{method:'POST',body:data});S.user=result.user;S.csrf=result.csrf;closeModal();await refresh();toast('Password updated.');
  }else if(type==='job'){
   const files=Array.from(form.querySelector('input[type=file]')?.files||[]);validateFiles(files,false);
   const id=Number(form.dataset.id);delete data.files;
   if(isRequester()){delete data.assignee_id;delete data.status;}else{data.assignee_id=data.assignee_id?Number(data.assignee_id):null;if(data.assignee_id&&data.status==='New')data.status='Assigned';}
   if(id)data.version=Number(form.dataset.version);
   const result=await api(id?'/api/jobs/'+id:'/api/jobs',{method:id?'PATCH':'POST',body:data});
   let photoError='';if(files.length){try{await uploadFiles(result.job.id,files,'Before','');}catch(error){photoError=error.message;}}
   closeModal();await refresh();await openJob(result.job.id);
   toast(photoError?'Job saved, but photos were not uploaded: '+photoError:id?'Job updated.':isRequester()?'Request submitted. Your admin will assign a technician.':'Job created and ready to go.',Boolean(photoError));
  }else if(type==='user'){
   const id=Number(form.dataset.id);if(id){data.active=data.active!=='false';if(id===S.user.id)data.role='admin';}
   const result=await api(id?'/api/users/'+id:'/api/users',{method:id?'PATCH':'POST',body:data});
   if(id===S.user.id)S.user=result.user;
   closeModal();await refresh();toast(id?'Team member updated.':'Account created. Share the sign-in email and temporary password privately.');
  }else if(type==='reset-password'){
   await api('/api/users/'+form.dataset.id,{method:'PATCH',body:{password:data.password}});closeModal();await refresh();toast('Password reset. Share the new temporary password privately.');
  }else if(type==='comment'){
   await api('/api/jobs/'+S.detail.job.id+'/comments',{method:'POST',body:{body:data.body}});await openJob(S.detail.job.id,'activity');await refresh(false);toast('Update added.');
  }else if(type==='photos'){
   const files=Array.from(form.querySelector('input[type=file]').files);validateFiles(files,true);
   await uploadFiles(S.detail.job.id,files,data.phase,data.caption);
   await refresh();await openJob(S.detail.job.id,'photos');toast('Photos uploaded.');
  }
 }catch(error){if(errorBox)errorBox.textContent=error.message;else toast(error.message,true);}
 finally{buttons.forEach(b=>b.disabled=false);}
}
function validateFiles(files,required){
 if(required&&!files.length)throw new Error('Choose at least one photo.');
 if(files.length>8)throw new Error('Choose up to 8 photos at a time.');
 if(files.some(f=>f.size>12*1024*1024))throw new Error('Each photo must be 12 MB or smaller.');
 if(files.reduce((n,f)=>n+f.size,0)>30*1024*1024)throw new Error('Upload up to 30 MB per batch. Split these photos into smaller groups.');
}
async function uploadFiles(id,files,phase,caption){
 const body=new FormData();files.forEach(file=>body.append('files',file));body.append('phase',phase);body.append('caption',caption);return api('/api/jobs/'+id+'/photos',{method:'POST',body});
}
const ACTIONS={
 retry:()=>init(),
 menu:()=>document.getElementById('sidebar').classList.toggle('open'),
 nav:async el=>{S.page=el.dataset.page;S.search='';S.assignee='';S.priority='';S.status='';await refresh();},
 view:el=>{S.view=el.dataset.view;render();},
 'new-job':el=>jobForm(null,el.dataset.status||'New'),
 'open-job':el=>openJob(Number(el.dataset.id)),
 'edit-job':()=>jobForm(S.detail.job),
 'back-job':()=>renderDetail(),
 'close-modal':()=>closeModal(),
 'detail-tab':el=>{S.detailTab=el.dataset.tab;renderDetail();},
 'new-user':()=>userForm(),
 'edit-user':el=>userForm(S.users.find(u=>u.id===Number(el.dataset.id))),
 'reset-password':el=>{const account=S.users.find(u=>u.id===Number(el.dataset.id));modal('Reset temporary password',account.name,`<form data-form="reset-password" id="reset-form" data-id="${account.id}"><div class="form-error" role="alert"></div><label class="field"><span class="label">New temporary password</span><input name="password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"><small>Share this privately. All current sessions will be signed out. The account holder must choose a new password at next login.</small></label></form>`,`<button class="btn" data-action="close-modal">Cancel</button><button class="btn primary" type="submit" form="reset-form">Reset password</button>`);},
 password:()=>passwordModal(),
 help:()=>help(),
 logout:async()=>{await api('/api/logout',{method:'POST'});S.user=null;S.jobs=[];S.users=[];S.page='overview';closeModal();await init();},
 'upload-photos':()=>modal('Add job photos','Capture the issue, the progress, or the finished work.',`<form data-form="photos" id="photos-form"><div class="form-error" role="alert"></div><div class="form-grid"><label class="field"><span class="label">Photo type</span><select name="phase">${options(isRequester()?['Before','General']:['Before','After','General'],!isRequester()&&S.detail.job.status==='Completed'?'After':'Before')}</select></label><label class="field"><span class="label">Caption (optional)</span><input name="caption" maxlength="500" placeholder="e.g. Replaced brake chamber"></label><div class="field full">${fileField('detail-files')}</div></div><p class="hint">Photos are resized for efficient storage. The full app removes embedded location metadata.</p></form>`,`<button class="btn" data-action="back-job">Cancel</button><button class="btn primary" type="submit" form="photos-form">${icon('upload')}Upload photos</button>`,false,'upload'),
 'archive-job':el=>{const archived=el.dataset.archived==='true';modal(archived?'Archive this job?':'Restore this job?',S.detail.job.title,`<p class="confirm-text">${archived?'The job will leave the active board. Its photos, comments, and history will be preserved in Archive.':'This job will return to the active board with its existing status and assignment.'}</p>`,`<button class="btn" data-action="back-job">Cancel</button><button class="btn primary" data-action="confirm-archive" data-archived="${archived}">${archived?'Archive job':'Restore job'}</button>`);},
 'confirm-archive':async el=>{await api('/api/jobs/'+S.detail.job.id+'/archive',{method:'POST',body:{archived:el.dataset.archived==='true'}});closeModal();await refresh();toast(el.dataset.archived==='true'?'Job archived.':'Job restored.');},
 'delete-photo':el=>modal('Delete this photo?','This action cannot be undone.',`<p class="confirm-text">Only this photo will be removed. The job and its remaining photos will stay in place.</p>`,`<button class="btn" data-action="back-job">Keep photo</button><button class="btn danger" data-action="confirm-delete-photo" data-id="${el.dataset.id}">Delete photo</button>`),
 'confirm-delete-photo':async el=>{await api('/api/photos/'+el.dataset.id,{method:'DELETE'});await refresh();await openJob(S.detail.job.id);toast('Photo deleted.');},
 lightbox:el=>{const p=S.detail.photos.find(x=>x.id===Number(el.dataset.id));S.modal='lightbox';overlayRoot.innerHTML=`<div class="overlay" role="dialog" aria-modal="true" aria-label="Photo preview"><button class="icon-btn lightbox-close" data-action="back-job" aria-label="Close photo">${icon('close')}</button><img class="photo-viewer" src="${esc(p.url)}" alt="${esc(p.caption||p.phase)}"></div>`;overlayRoot.querySelector('button').focus();},
 notifications:async()=>{modal('Notifications','Assignments and status changes in your workspace.',S.notifications.length?S.notifications.map(n=>`<button class="notification ${n.seen?'seen':''}" data-action="open-job" data-id="${n.job_id}"><i class="dot"></i><span>${esc(n.body)}<small>${longDate(n.created_at)}</small></span></button>`).join(''):'<p class="hint">You\'re all caught up. New assignments and status updates will appear here.</p>');await api('/api/notifications/read',{method:'POST'});S.notifications.forEach(n=>n.seen=1);document.querySelector('.notif-dot')?.remove();},
 export:async()=>{if(DEMO){window.demoExport();return;}const response=await fetch('/api/export',{credentials:'same-origin'});if(!response.ok)throw new Error('Export failed. Sign in again and retry.');const url=URL.createObjectURL(await response.blob());download(url,'18wheelers-jobs.csv');},
 'demo-switch':async el=>{window.demoSwitch(el.dataset.role);closeModal();S.page='overview';S.search='';S.assignee='';S.priority='';S.status='';await init();toast(roleSummary());},
 'demo-reset':()=>modal('Reset the demo?','Only this browser\'s demonstration will change.','<p class="confirm-text">This removes your local demo edits and uploaded photos, then restores the sample jobs.</p>','<button class="btn" data-action="close-modal">Cancel</button><button class="btn primary" data-action="confirm-demo-reset">Reset demo</button>'),
 'confirm-demo-reset':async()=>{window.demoReset();closeModal();S.page='overview';S.search='';S.assignee='';S.priority='';S.status='';await init();toast('Demo reset.');}
};
function download(url,name){const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
document.addEventListener('click',event=>{
 const el=event.target.closest('[data-action]');if(el){event.preventDefault();const action=ACTIONS[el.dataset.action];if(action)run(()=>action(el));}
});
document.addEventListener('submit',event=>{const form=event.target.closest('form[data-form]');if(form){event.preventDefault();submitForm(form);}});
document.addEventListener('input',event=>{if(event.target.id==='job-search'){S.search=event.target.value;document.getElementById('jobs-view').innerHTML=jobsView();}});
document.addEventListener('change',event=>{
 const el=event.target;const filters={'filter-assignee':'assignee','filter-priority':'priority','filter-status':'status'};
 if(filters[el.id]){S[filters[el.id]]=el.value;document.getElementById('jobs-view').innerHTML=jobsView();}
 if(el.id==='detail-status')run(async()=>{try{const result=await api('/api/jobs/'+S.detail.job.id,{method:'PATCH',body:{status:el.value,version:S.detail.job.version}});S.detail.job=result.job;renderDetail();await refresh();toast('Status updated.');}catch(e){el.value=S.detail.job.status;throw e;}});
 if(el.type==='file'){const count=el.files.length;const summary=el.parentElement.querySelector('.file-summary');if(summary)summary.textContent=count?`${count} photo${count===1?'':'s'} selected`:'';}
});
document.addEventListener('keydown',event=>{
 if(event.key==='Escape'&&S.modal){if(S.modal==='lightbox')renderDetail();else closeModal();}
 if(event.key==='Enter'&&event.target.matches('tr[data-action]'))event.target.click();
 if(event.key==='Tab'&&S.modal){const items=[...overlayRoot.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]')].filter(x=>x.offsetParent!==null);const first=items[0],last=items.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}
});
setInterval(()=>{if(S.user&&!S.user.must_change&&!S.modal&&!document.hidden){const focused=document.activeElement;if(!focused||!['INPUT','SELECT','TEXTAREA'].includes(focused.tagName))refresh().catch(()=>{});}},30000);
init();
