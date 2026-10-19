'use strict';
const $ = id => document.getElementById(id);
const el = (tag, text = '', cls = '') => {const n = document.createElement(tag); n.textContent = text; n.className = cls; return n;};
let csrf = '', workspace = '', role = '', page = 1, total = 0, activePost = null, members = [], version = 0, poll = null, jobStates = '';
const base = () => '/api/w/' + workspace;
const canWrite = () => role !== 'viewer';
const message = text => $('message').textContent = text;
const params = () => new URLSearchParams({q:$('search').value, sentiment:$('sentiment').value, source:$('source-filter').value, start:$('start').value, end:$('end').value});
async function api(url, options = {}) {
  const headers = {...options.headers};
  if (options.method && options.method !== 'GET') headers['X-CSRF-Token'] = csrf;
  if (options.json !== undefined) {headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.json);}
  const response = await fetch(url, {...options, headers});
  const data = await response.json().catch(() => ({detail:'Request failed (' + response.status + ').'}));
  if (!response.ok) {if (response.status === 401 && !url.includes('/auth/')) showAuth(); throw new Error(Array.isArray(data.detail) ? data.detail.map(i => i.msg).join('; ') : data.detail || 'Request failed.');}
  return data;
}
const action = fn => async event => {event?.preventDefault(); try {await fn(event);} catch (error) {message(error.message);}};
function showAuth() {$('auth').hidden = false; $('application').hidden = true; clearInterval(poll); csrf = '';}
async function initialize() {
  const me = await api('/api/me'); csrf = me.csrf; $('auth').hidden = true; $('application').hidden = false; $('user-name').textContent = me.name;
  $('analysis-status').textContent=me.analysis.description+' · Statistical topics · Human review. Existing records retain their original model until reanalyzed.';
  $('research-status').textContent=me.research.provider==='ollama'?'Local generative research with '+me.research.model+'. Answers cite retrieved posts. Check every claim against its evidence.':'Local extractive research: retrieves relevant posts and summarizes their sentiment. No generated explanations.';
  $('workspace').replaceChildren(...me.workspaces.map(w => {const o = el('option', w.name); o.value = w.id; o.dataset.role = w.role; return o;}));
  if (me.workspaces.some(w => w.id === workspace)) $('workspace').value = workspace;
  await changeWorkspace(); clearInterval(poll);
  poll = setInterval(() => {if (!document.hidden && !$('application').hidden) refreshJobs().catch(error => message(error.message));}, 4000);
}
async function changeWorkspace() {
  workspace = $('workspace').value; role = $('workspace').selectedOptions[0].dataset.role; page = 1; version++; jobStates = '';
  $('role').textContent = role; document.querySelectorAll('[data-write]').forEach(n => n.hidden = !canWrite()); document.querySelectorAll('[data-owner]').forEach(n => n.hidden = role !== 'owner');
  $('answer').replaceChildren(); $('filters').reset(); $('review-dialog').close();
  await Promise.all([load(), activity(), loadMembers(), loadConnectors(), refreshJobs()]);
}
function mixRow(name, value, maximum) {const row = el('div', '', 'mix-row'); row.append(el('span', name), el('strong', value)); const meter = document.createElement('progress'); meter.max = maximum || 1; meter.value = value; meter.setAttribute('aria-label', name); row.append(meter); return row;}
async function load() {
  const current = ++version, selected = workspace, data = await api(base()+'/posts?'+params()+'&page='+page); if (current !== version || selected !== workspace) return;
  const s = data.summary; total = s.total; $('total').textContent = total; $('positive').textContent = s.sentiment.positive; $('negative').textContent = s.sentiment.negative; $('neutral').textContent = s.sentiment.neutral+s.sentiment.unclassified; $('unclassified').textContent = s.sentiment.unclassified+' unclassified';
  $('mix').replaceChildren(...Object.entries(s.sentiment).map(([k,v]) => mixRow(k,v,total)));
  $('topics').replaceChildren(...s.topics.map(t => el('span', t.name+' · '+t.count, 'topic')));
  if (!s.topics.length) $('topics').append(el('p','Import data to discover topics.','muted'));
  $('timeline').replaceChildren(...s.timeline.slice(-14).map(d => mixRow(d.date+' · '+d.negative+' negative', d.total, Math.max(...s.timeline.map(i => i.total)))));
  $('sources').replaceChildren(...s.sources.map(s => mixRow(s.name+' · '+s.negative+' negative',s.total,total)));
  $('posts').replaceChildren(...data.posts.map(postCard)); if (!data.posts.length) $('posts').append(el('p','No conversations found. Import data or adjust the filters.','empty'));
  $('previous').disabled = page <= 1; $('next').disabled = page*25 >= total; $('page-info').textContent = `Page ${page} / ${Math.max(1,Math.ceil(total/25))} · ${total} conversations`; $('export').href = base()+'/export?'+params();
}
function postCard(post) {
  const card = el('article','','post'); card.id = 'post-'+post.id; const meta = el('div','','post-meta');
  meta.append(el('strong',post.source),el('span',post.published_at || 'No date supplied'),el('span',post.language),el('span',post.sentiment+(post.reviewed?' · reviewed':''),'badge '+post.sentiment)); card.append(meta,el('p',post.text));
  const detail = el('div','','post-meta'); detail.append(el('span',post.intent+' · '+post.status),el('span',post.assignee || 'Unassigned')); Object.entries(post.aspects || {}).forEach(([k,v]) => detail.append(el('span',k+': '+v)));
  if (canWrite()) {const b = el('button','Review / assign','secondary'); b.addEventListener('click',() => openReview(post)); detail.append(b);} card.append(detail); return card;
}
async function activity() {
  const selected = workspace, data = await api(base()+'/activity'); if (selected !== workspace) return;
  $('monitors').replaceChildren(...data.monitor.map(m => el('span',`${m.name} · “${m.keyword}” · ≥${m.threshold}`,'topic')));
  $('alerts').replaceChildren(...data.alert.map(a => {const n = el('article','','post'); n.append(el('h3',a.title+' · '+a.status),el('p',a.detail)); if (a.status==='open' && canWrite()) {const b = el('button','Acknowledge','secondary'); b.addEventListener('click',action(async () => {await api(base()+'/alerts/'+a.id+'/acknowledge',{method:'POST'}); await activity();})); n.append(b);} return n;}));
  if (!data.alert.length) $('alerts').append(el('p','No alerts. Create a monitor to watch matching conversations.','muted'));
  $('report-list').replaceChildren(...data.report.map(r => {const n = el('article','','post'); n.append(el('strong',r.name),el('p',r.created_at+' · '+r.summary.total+' conversations')); const b = el('button','Download JSON','secondary'); b.addEventListener('click',() => download(r)); n.append(b); return n;}));
  $('audit').replaceChildren(...data.audit.slice(0,15).map(a => el('p',`${a.created_at.slice(0,19)} · ${a.actor} · ${a.action}`,'audit-row')));
  $('comparisons').replaceChildren(...data.competitor.map(c=>mixRow(c.name+' · '+c.positive+' positive / '+c.negative+' negative',c.total,Math.max(1,...data.competitor.map(i=>i.total)))));
  const schedule=data.schedule[0]; $('schedule-status').textContent=schedule?.enabled?'Automatic reports every '+schedule.interval_hours+' hours. Next: '+new Date(schedule.next_run*1000).toLocaleString():'Automatic reports are off. The server must remain running to create scheduled reports.';
  if(schedule){$('schedule-hours').value=schedule.interval_hours;$('schedule-enabled').checked=schedule.enabled;}
}
function download(report) {const url = URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'})); const a = el('a'); a.href=url; a.download='social-ear-report.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url),1000);}
async function refreshJobs() {
  const selected = workspace, jobs = await api(base()+'/jobs'); if (selected !== workspace) return;
  const state = selected+JSON.stringify(jobs.map(j => [j.id,j.state]));
  $('jobs').replaceChildren(...jobs.map(j => {const n = el('div','','job-row'); n.append(el('strong',j.kind),el('span',j.state,'badge'),el('span',j.result.error || (j.state==='completed'?JSON.stringify(j.result):'Queued processing'))); if (j.state==='failed' && canWrite()) {const b=el('button','Retry','secondary'); b.addEventListener('click',action(async () => {await api(base()+'/jobs/'+j.id+'/retry',{method:'POST'}); await refreshJobs();})); n.append(b);} return n;}));
  if (jobStates && jobStates!==state) await Promise.all([load(),activity()]); jobStates=state;
}
async function loadMembers() {const selected=workspace, data=await api(base()+'/members'); if(selected!==workspace)return; members=data; $('members').replaceChildren(...members.map(m=>el('p',m.email+' · '+m.role,'audit-row')));}
async function loadConnectors() {const selected=workspace, data=await api(base()+'/connectors'); if(selected!==workspace)return; $('connector-status').textContent=data.bluesky?'Public search enabled.':'Disabled. An administrator can enable Bluesky in server configuration.'; $('connector-form').hidden=!data.bluesky || !canWrite();}
function openReview(post) {
  activePost=post; $('review-text').textContent=post.text; $('review-sentiment').value=post.sentiment; $('review-status').value=post.status;
  const empty=el('option','Unassigned'); empty.value=''; $('review-assignee').replaceChildren(empty,...members.map(m=>{const o=el('option',m.email);o.value=m.email;return o;})); $('review-assignee').value=post.assignee; $('review-note').value=''; $('review-error').textContent='';
  $('review-notes').replaceChildren(...post.notes.map(n=>el('p',n.author+': '+n.text))); $('review-dialog').showModal();
}
$('auth-form').addEventListener('submit',async event=>{event.preventDefault(); const mode=event.submitter?.value || 'login'; $('auth-message').textContent='Please wait…'; const buttons=[...event.currentTarget.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true); try {await api('/api/auth/'+mode,{method:'POST',json:{email:$('email').value,password:$('password').value,name:$('name').value}});$('password').value='';await initialize();$('auth-message').textContent='';}catch(e){$('auth-message').textContent=e.message;}finally{buttons.forEach(b=>b.disabled=false);}});
$('logout').addEventListener('click',action(async()=>{await api('/api/auth/logout',{method:'POST'});showAuth();}));
$('workspace').addEventListener('change',action(changeWorkspace));
$('filters').addEventListener('submit',action(async()=>{page=1;await load();}));
$('filters').addEventListener('reset',()=>setTimeout(action(async()=>{page=1;await load();}),0));
$('previous').addEventListener('click',action(async()=>{if(page>1)page--;await load();}));
$('next').addEventListener('click',action(async()=>{if(page*25<total)page++;await load();}));
$('upload').addEventListener('submit',action(async()=>{const f=$('file').files[0];if(!f)return;if(f.size>2*1024*1024)throw new Error('Choose a CSV smaller than 2 MB.');await api(base()+'/import',{method:'POST',headers:{'Content-Type':'text/csv'},body:await f.text()});message('Import queued. Check processing history for results.');$('file').value='';await refreshJobs();}));
$('ask-form').addEventListener('submit',action(async()=>{const selected=workspace;$('answer').textContent='Finding evidence…';try{const r=await api(base()+'/research',{method:'POST',json:{question:$('question').value}});if(selected!==workspace)return;$('answer').replaceChildren(el('p',r.answer),el('small',r.notice || r.method),...r.citations.map(c=>{const n=el('blockquote');n.append(el('p',c.text),el('small',c.source+' · evidence '+c.id));return n;}));}catch(error){$('answer').textContent=error.message;throw error;}}));
$('monitor-form').addEventListener('submit',action(async()=>{await api(base()+'/monitors',{method:'POST',json:{name:$('monitor-name').value,keyword:$('keyword').value,threshold:Number($('threshold').value),sentiment:$('monitor-sentiment').value}});message('Monitor saved.');await activity();}));
$('create-report').addEventListener('click',action(async()=>{await api(base()+'/reports',{method:'POST'});message('Report queued.');await refreshJobs();}));
$('reanalyze').addEventListener('click',action(async()=>{await api(base()+'/reanalyze',{method:'POST'});message('Reanalysis queued. Human-reviewed sentiments are preserved.');await refreshJobs();}));
$('competitor-form').addEventListener('submit',action(async()=>{await api(base()+'/competitors',{method:'POST',json:{name:$('competitor-name').value,keyword:$('competitor-keyword').value}});message('Comparison saved.');await activity();}));
$('schedule-form').addEventListener('submit',action(async()=>{await api(base()+'/report-schedule',{method:'POST',json:{interval_hours:Number($('schedule-hours').value),enabled:$('schedule-enabled').checked}});message('Report schedule saved.');await activity();}));
$('connector-form').addEventListener('submit',action(async()=>{await api(base()+'/connectors/bluesky',{method:'POST',json:{query:$('connector-query').value}});message('Collection queued.');await refreshJobs();}));
$('workspace-form').addEventListener('submit',action(async()=>{const r=await api('/api/workspaces',{method:'POST',json:{name:$('workspace-name').value}});workspace=r.id;await initialize();}));
$('member-form').addEventListener('submit',action(async()=>{await api(base()+'/members',{method:'POST',json:{email:$('member-email').value,role:$('member-role').value}});message('Team membership saved.');await loadMembers();}));
$('close-review').addEventListener('click',()=>$('review-dialog').close());
$('review-form').addEventListener('submit',async e=>{e.preventDefault();try{await api(base()+'/posts/'+activePost.id,{method:'PATCH',json:{sentiment:$('review-sentiment').value,status:$('review-status').value,assignee:$('review-assignee').value,note:$('review-note').value}});$('review-dialog').close();await Promise.all([load(),activity()]);}catch(error){$('review-error').textContent=error.message;}});
initialize().catch(error=>{showAuth();if(!error.message.includes('Sign in'))$('auth-message').textContent=error.message;});
