const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let latestAnalysis = null;
let toastTimer = null;
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const dateFmt = (v) => { if(!v) return "—"; const d=new Date(v); return Number.isNaN(d.getTime())?v:d.toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric"}); };
const timeFmt = (v) => { if(!v) return ""; const d=new Date(v); return Number.isNaN(d.getTime())?v:d.toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}); };
const statusClass = s => "status-" + String(s).replace(/\s+/g,"-");
const priorityClass = s => "priority-" + String(s);
async function api(url, options={}) {
  const res = await fetch(url, {headers:{"Content-Type":"application/json",...(options.headers||{})}, ...options});
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}
function toast(msg){ const el=$("#toast");el.textContent=msg;el.classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove("show"),3200); }
function showView(view){
  $$(".view").forEach(v=>v.classList.toggle("active",v.id===`view-${view}`));
  $$(".nav-item").forEach(n=>n.classList.toggle("active",n.dataset.view===view));
  $("#crumbCurrent").textContent=({home:"Overview",tickets:"Ticket inbox",new:"Create a ticket"})[view]||"Overview";
  if(view==="home") loadDashboard();
  if(view==="tickets") loadTickets();
  window.scrollTo({top:0,behavior:"smooth"});
}
document.addEventListener("click",e=>{
  const nav=e.target.closest("[data-view]");
  if(nav){e.preventDefault();showView(nav.dataset.view);}
});
function ticketRow(t){
  return `<div class="ticket-row" data-ticket="${t.id}">
    <div><div class="ticket-title">#CC-${String(t.id).padStart(4,"0")} · ${esc(t.title)}</div>
    <div class="ticket-meta"><span>${esc(t.name)}</span><span>·</span><span>${esc(t.category)}</span><span>·</span><span>${dateFmt(t.created_at)}</span></div></div>
    <div class="row-right"><span class="priority ${priorityClass(t.priority)}">${esc(t.priority)}</span><span class="status-pill ${statusClass(t.status)}">${esc(t.status)}</span></div>
  </div>`;
}
async function loadHealth(){
  try{
    const h=await api("/api/health");
    $("#connectionDot").classList.toggle("online",h.nexus_configured);
    $("#connectionText").textContent=h.nexus_configured?`Nexus connected · ${h.model}`:"Local fallback mode";
  }catch{ $("#connectionText").textContent="Backend unavailable"; }
}
async function loadDashboard(){
  try{
    const s=await api("/api/stats");
    $("#statTotal").textContent=s.total;$("#statOpen").textContent=s.open;$("#statProgress").textContent=s.in_progress;$("#statResolved").textContent=s.resolved;
    $("#highPriority").textContent=`${s.high_priority} high-priority`;
    $("#navCount").textContent=s.open;
    $("#recentTickets").innerHTML=s.recent.length?s.recent.map(ticketRow).join(""):`<div class="empty-state">No tickets yet. Create your first support request to see it here.</div>`;
    const cats=s.categories;
    const max=Math.max(1,...cats.map(c=>c.count));
    $("#categoryBars").innerHTML=cats.length?cats.slice(0,5).map(c=>`<div><div class="bar-label"><span>${esc(c.category)}</span><strong>${c.count}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(5,c.count/max*100)}%"></div></div></div>`).join(""):`<div class="muted">No data yet. Submit a ticket to get started.</div>`;
  }catch(e){toast(e.message);}
}
let searchTimer;
async function loadTickets(){
  const params=new URLSearchParams();
  if($("#statusFilter").value)params.set("status",$("#statusFilter").value);
  if($("#categoryFilter").value)params.set("category",$("#categoryFilter").value);
  if($("#searchInput").value.trim())params.set("q",$("#searchInput").value.trim());
  try{
    const tickets=await api("/api/tickets?"+params.toString());
    $("#ticketCountText").textContent=`${tickets.length} ticket${tickets.length===1?"":"s"}`;
    $("#navCount").textContent=tickets.filter(t=>t.status==="Open").length;
    $("#ticketTableBody").innerHTML=tickets.length?tickets.map(t=>`<tr data-ticket="${t.id}">
      <td><strong>#CC-${String(t.id).padStart(4,"0")}</strong><small>${esc(t.title)}</small></td>
      <td><strong>${esc(t.name)}</strong><small>${esc(t.email)}</small></td>
      <td><strong>${esc(t.category)}</strong><small>${esc(t.department)}</small></td>
      <td><span class="priority ${priorityClass(t.priority)}">${esc(t.priority)}</span></td>
      <td><span class="status-pill ${statusClass(t.status)}">${esc(t.status)}</span></td>
      <td>${dateFmt(t.created_at)}</td><td>→</td></tr>`).join(""):`<tr><td colspan="7" class="empty-state">No tickets match these filters.</td></tr>`;
  }catch(e){toast(e.message);}
}
async function loadCategories(){
  try{
    const m=await api("/api/meta");
    $("#categoryFilter").innerHTML='<option value="">All categories</option>'+m.categories.map(c=>`<option>${esc(c.name)}</option>`).join("");
  }catch{}
}
function renderAnalysis(a){
  latestAnalysis=a;
  $("#analysisMode").textContent=a.mode||"Analysis complete";
  $("#previewStatus").textContent="ANALYSED";
  $("#previewStatus").style.background="#eaf8f1";$("#previewStatus").style.color="#299674";
  $("#previewHint").classList.add("hidden");
  $("#analysisResult").classList.remove("hidden");
  $("#analysisResult").innerHTML=`
    <div class="result-cell"><small>Suggested category</small><strong>${esc(a.category)}</strong></div>
    <div class="result-cell"><small>Recommended department</small><strong>${esc(a.department)}</strong></div>
    <div class="result-cell"><small>Suggested priority</small><strong><span class="priority ${priorityClass(a.priority)}">${esc(a.priority)}</span></strong></div>
    <div class="result-cell"><small>AI mode</small><strong>${a.ai_used?"Nexus AI":"Local fallback"}</strong></div>
    <div class="result-cell wide"><small>Clearer ticket description</small><p>${esc(a.improved_description)}</p></div>`;
}
async function runAnalysis(){
  const title=$("#issueTitle").value.trim(), description=$("#issueDescription").value.trim(), role=$('[name="role"]').value;
  if(title.length<4||description.length<10){$("#formMessage").textContent="Enter a title and at least 10 characters describing the issue first.";return;}
  const btn=$("#analyzeBtn");btn.disabled=true;btn.innerHTML="◌ Analysing…";$("#formMessage").textContent="";
  try{
    const a=await api("/api/analyze",{method:"POST",body:JSON.stringify({title,description,role})});
    renderAnalysis(a);if(a.notice)toast(a.notice);else toast("Issue analysis completed.");
  }catch(e){$("#formMessage").textContent=e.message;}
  finally{btn.disabled=false;btn.innerHTML="<span>✦</span> Analyse with AI";}
}
$("#analyzeBtn").addEventListener("click",runAnalysis);
$("#issueDescription").addEventListener("input",()=>{$("#charCount").textContent=`${$("#issueDescription").value.length} / 4000`;latestAnalysis=null;});
$("#issueTitle").addEventListener("input",()=>{latestAnalysis=null;});
$("#ticketForm").addEventListener("submit",async e=>{
  e.preventDefault();
  const form=new FormData(e.currentTarget), payload=Object.fromEntries(form.entries());
  const btn=$("#submitBtn");btn.disabled=true;btn.textContent="Submitting…";$("#formMessage").textContent="";
  try{
    const t=await api("/api/tickets",{method:"POST",body:JSON.stringify(payload)});
    $("#formMessage").className="form-message success";
    $("#formMessage").textContent=`Ticket #CC-${String(t.id).padStart(4,"0")} submitted successfully.`;
    toast(`Ticket #CC-${String(t.id).padStart(4,"0")} created`);
    e.currentTarget.reset();$("#charCount").textContent="0 / 4000";latestAnalysis=null;
    $("#analysisResult").classList.add("hidden");$("#previewHint").classList.remove("hidden");$("#previewStatus").textContent="NOT RUN";$("#analysisMode").textContent="Ready when you are";
    await loadDashboard();
    setTimeout(()=>showView("tickets"),900);
  }catch(err){$("#formMessage").className="form-message";$("#formMessage").textContent=err.message;}
  finally{btn.disabled=false;btn.innerHTML='Submit ticket <span>→</span>';}
});
$("#searchInput").addEventListener("input",()=>{clearTimeout(searchTimer);searchTimer=setTimeout(loadTickets,220);});
$("#statusFilter").addEventListener("change",loadTickets);$("#categoryFilter").addEventListener("change",loadTickets);
$("#refreshBtn").addEventListener("click",async()=>{await loadHealth();await loadDashboard();if($("#view-tickets").classList.contains("active"))await loadTickets();toast("Workspace refreshed");});
document.addEventListener("click",e=>{const el=e.target.closest("[data-ticket]");if(el)openTicket(el.dataset.ticket);});
async function openTicket(id){
  try{
    const t=await api(`/api/tickets/${id}`);
    $("#modalTicketId").textContent=`TICKET #CC-${String(t.id).padStart(4,"0")}`;
    $("#modalTitle").textContent=t.title;
    $("#modalBody").innerHTML=`
      <div class="detail-grid">
        <div class="detail-box"><small>Requester</small><strong>${esc(t.name)}</strong></div>
        <div class="detail-box"><small>Email</small><strong>${esc(t.email)}</strong></div>
        <div class="detail-box"><small>Category</small><strong>${esc(t.category)}</strong></div>
        <div class="detail-box"><small>Assigned department</small><strong>${esc(t.department)}</strong></div>
        <div class="detail-box"><small>Priority</small><span class="priority ${priorityClass(t.priority)}">${esc(t.priority)}</span></div>
        <div class="detail-box"><small>Current status</small><span class="status-pill ${statusClass(t.status)}">${esc(t.status)}</span></div>
      </div>
      <div class="detail-section"><h3>Original description</h3><p>${esc(t.description)}</p></div>
      <div class="detail-section"><h3>AI-improved description</h3><p>${esc(t.improved_description)}</p></div>
      <div class="detail-section"><h3>AI routing note</h3><p>${esc(t.ai_summary)}</p></div>
      <div class="detail-section"><h3>Activity history</h3>${(t.activity||[]).map(a=>`<div class="activity-item">${esc(a.message)} · ${esc(timeFmt(a.created_at))}</div>`).join("")}</div>
      <div class="modal-actions">
        <label>Update status<select id="modalStatus">${["Open","In Progress","Resolved","Closed"].map(s=>`<option ${s===t.status?"selected":""}>${s}</option>`).join("")}</select></label>
        <label>Priority<select id="modalPriority">${["Low","Medium","High","Urgent"].map(s=>`<option ${s===t.priority?"selected":""}>${s}</option>`).join("")}</select></label>
        <button class="primary-button" id="saveTicket" data-id="${t.id}">Save changes</button>
      </div>`;
    $("#ticketModal").classList.remove("hidden");
    $("#saveTicket").addEventListener("click",async()=>{
      const save=$("#saveTicket");save.disabled=true;save.textContent="Saving…";
      try{await api(`/api/tickets/${t.id}`,{method:"PATCH",body:JSON.stringify({status:$("#modalStatus").value,priority:$("#modalPriority").value})});$("#ticketModal").classList.add("hidden");toast("Ticket updated");await loadDashboard();if($("#view-tickets").classList.contains("active"))await loadTickets();}
      catch(err){toast(err.message);}finally{save.disabled=false;save.textContent="Save changes";}
    });
  }catch(e){toast(e.message);}
}
$("#closeModal").addEventListener("click",()=>$("#ticketModal").classList.add("hidden"));
$("#ticketModal").addEventListener("click",e=>{if(e.target===$("#ticketModal"))$("#ticketModal").classList.add("hidden");});
document.addEventListener("keydown",e=>{if(e.key==="Escape")$("#ticketModal").classList.add("hidden");});
(async()=>{await loadHealth();await loadCategories();await loadDashboard();})();
