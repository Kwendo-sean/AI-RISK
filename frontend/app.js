"use strict";

const API = "/api/v2";
const STORAGE_KEY = "career-survival-session-v1";
const QUEST_KEY = "career-survival-quests-v1";
const CONSTRUCT_LABELS = {routine_intensity:"Repetitive work",physical_presence:"Hands-on work",human_trust:"Trust with people",accountability:"Who answers for decisions",creative_originality:"Original ideas",data_handling:"Working with information",analytical_reasoning:"Judgement calls",ai_adoption:"Using AI today",communication:"Explaining things clearly",negotiation:"Negotiating",regulation_compliance:"Rules and regulation",safety_judgment:"Safety decisions",emotional_intelligence:"Reading people",local_knowledge:"Local know-how",entrepreneurship:"Running your own work",client_interaction:"Working with clients",learning_adaptability:"Learning new things",domain_expertise:"Depth of experience",work_environment:"Changing conditions",income_model:"How you get paid",leadership:"Leading people",recent_transformation:"Recent changes at work"};
const PHASES = ["Briefing", "Profile", "Identity", "Career map", "Scanning", "Battle", "Strategy"];
const ROUTES = ["landing", "onboarding", "avatar", "assessment", "scan", "battle", "results", "error"];
const state = {meta:null, credentials:null, profile:null, assessment:null, selectedCareer:null, editing:false, camera:null, scanTimer:null, battleIndex:0, retry:null};
const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

function storedCredentials(){try{return JSON.parse(localStorage.getItem(STORAGE_KEY)||"null");}catch{return null;}}
function storeCredentials(value){state.credentials=value;if(value)localStorage.setItem(STORAGE_KEY,JSON.stringify(value));else localStorage.removeItem(STORAGE_KEY);}
function questStore(){try{return JSON.parse(localStorage.getItem(QUEST_KEY)||"{}");}catch{return {};}}
function startedQuests(){const id=state.assessment?.assessment_id;const list=id?questStore()[id]:null;return Array.isArray(list)?list:[];}
function rememberQuest(skillId){const id=state.assessment?.assessment_id;if(!id)return;const store=questStore();store[id]=[...new Set([...(Array.isArray(store[id])?store[id]:[]),skillId])];try{localStorage.setItem(QUEST_KEY,JSON.stringify(store));}catch{}}
function authHeaders(){return state.credentials?{"X-Session-Token":state.credentials.access_token}:{}}
async function request(path, options={}){
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),10000);
  try{
    const response=await fetch(API+path,{...options,signal:controller.signal,headers:{"Content-Type":"application/json",...authHeaders(),...(options.headers||{})}});
    if(response.status===204)return null;
    let data=null;try{data=await response.json();}catch{data={detail:"The server returned an unreadable response."};}
    if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"Request failed");
    return data;
  }finally{clearTimeout(timeout);}
}
function announce(message){$("#live-region").textContent="";setTimeout(()=>$("#live-region").textContent=message,30);}
function toast(message){const el=$("#toast");el.textContent=message;el.classList.add("show");clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.remove("show"),2800);}
function track(event_name, properties={}){
  const anonymous_id=state.credentials?.session_id||storedCredentials()?.session_id||crypto.randomUUID();
  fetch(API+"/analytics",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({anonymous_id,event_name,properties})}).catch(()=>{});
}
function stopCamera(){if(state.camera){state.camera.getTracks().forEach(track=>track.stop());state.camera=null;}}
const ROUTE_GUARDS={
  landing:()=>true,
  onboarding:()=>true,
  error:()=>true,
  avatar:()=>!!(state.profile&&state.credentials),
  assessment:()=>!!state.assessment,
  scan:()=>!!state.assessment?.result,
  battle:()=>!!state.assessment?.result,
  results:()=>!!state.assessment?.result
};
function furthestRoute(){
  if(state.assessment?.result)return "results";
  if(state.assessment)return "assessment";
  if(state.profile&&state.credentials)return "avatar";
  return "landing";
}
function navigate(name, push=true){
  if(!ROUTES.includes(name))name="landing";
  if(!(ROUTE_GUARDS[name]||(()=>false))()){
    const allowed=furthestRoute();
    if(allowed!==name){
      history.replaceState({screen:allowed},"",`#/${allowed}`);
      toast(allowed==="landing"?"Start a scan to reach that screen.":"Finish the current step first.");
      name=allowed;push=false;
    }
  }
  stopCamera();clearTimeout(state.scanTimer);
  $$(".screen").forEach(screen=>screen.classList.toggle("active",screen.id===`screen-${name}`));
  const screen=$(`#screen-${name}`);const phase=Number(screen?.dataset.phase||0);
  $("#phase-label").textContent=PHASES[phase]||"Mission";$("#phase-fill").style.width=`${phase/6*100}%`;$("#phase-count").textContent=`${String(phase).padStart(2,"0")} / 06`;
  $("#profile-menu").classList.toggle("hidden",!state.profile||name==="onboarding");
  if(push&&location.hash!==`#/${name}`)history.pushState({screen:name},"",`#/${name}`);
  scrollTo({top:0,behavior:reducedMotion?"auto":"smooth"});setTimeout(()=>$("#main").focus({preventScroll:true}),20);
}
function fail(message,retry){state.retry=retry;$("#error-message").textContent=message;track("error",{screen:location.hash.slice(2)||"unknown",error_code:"request_failed"});navigate("error");}
function setBusy(button,busy,label="Working…"){if(!button)return;button.disabled=busy;if(busy){button.dataset.label=button.textContent;button.textContent=label;}else if(button.dataset.label){button.textContent=button.dataset.label;delete button.dataset.label;}}
function eventId(type,key=""){return `${(state.assessment?.assessment_id||"none").slice(0,8)}-${type}-${key||crypto.randomUUID()}`.slice(0,80);}
async function gameEvent(type,payload={},key=""){
  if(!state.assessment)return null;
  try{return await request(`/profiles/${state.credentials.session_id}/assessments/${state.assessment.assessment_id}/game-events`,{method:"POST",body:JSON.stringify({event_id:eventId(type,key),event_type:type,payload})});}catch{return null;}
}

function wireHeroImage(){const image=$("#hero-image"),frame=$("#hero-visual");if(!image||!frame)return;
  image.addEventListener("load",()=>{if(image.naturalWidth)frame.classList.remove("empty");});
  image.addEventListener("error",()=>frame.classList.add("empty"));
  if(image.complete&&image.naturalWidth)frame.classList.remove("empty");}
async function boot(){
  wireHeroImage();
  state.credentials=storedCredentials();
  try{
    state.meta=await request("/meta");
    $("#career-count").textContent=`${state.meta.career_count}`;
    fillSelect($("#career-stage"),state.meta.career_stages);
    fillSelect($("#industry"),state.meta.industries);
  }catch{$("#career-count").textContent="140+";}
  if(state.credentials)$("#resume-button").classList.remove("hidden");
  const route=location.hash.replace("#/","");navigate(route==="landing"?"landing":"landing",false);
}
function fillSelect(select,values=[]){values.forEach(value=>{const option=document.createElement("option");option.value=value;option.textContent=value;select.append(option);});}

async function resume(){
  if(!state.credentials)return navigate("onboarding");
  try{
    const data=await request(`/profiles/${state.credentials.session_id}`);state.profile=data.profile;state.assessment=data.assessment;
    state.selectedCareer=data.assessment?.career||null;
    if(!state.assessment){navigate("avatar");return;}
    if(state.assessment.status==="complete"){renderResults();navigate("results");track("result_viewed",{screen:"results",career_id:state.assessment.career.id});}
    else{renderQuestion();navigate("assessment");}
  }catch(error){storeCredentials(null);state.profile=null;state.assessment=null;toast("Saved mission expired. Start a new scan.");navigate("onboarding");}
}

let searchTimer=null,searchController=null;
$("#career-search").addEventListener("input",()=>{
  clearTimeout(searchTimer);state.selectedCareer=null;$("#selected-career").classList.add("hidden");
  const q=$("#career-search").value.trim();
  if(q.length<2){closeCareerResults();return;}
  searchTimer=setTimeout(()=>searchCareer(q),180);
});
$("#career-search").addEventListener("keydown",event=>{
  const options=$$(".career-option",$("#career-results"));
  if(event.key==="ArrowDown"&&options.length){event.preventDefault();options[0].focus();}
  if(event.key==="Escape")closeCareerResults();
});
async function searchCareer(q){
  if(searchController)searchController.abort();searchController=new AbortController();
  const results=$("#career-results");results.classList.remove("hidden");results.replaceChildren();
  const loading=document.createElement("p");loading.className="field-hint";loading.textContent="Searching career signals…";results.append(loading);
  try{
    const data=await request(`/careers?q=${encodeURIComponent(q)}&limit=12`);results.replaceChildren();track("career_searched",{query_length:q.length});
    if(!data.careers.length){const empty=document.createElement("p");empty.className="field-hint";empty.textContent="No close match. Describe the work below for a task-led assessment.";results.append(empty);track("career_not_found",{query_length:q.length});return;}
    data.careers.forEach((career,index)=>{
      const button=document.createElement("button");button.type="button";button.className="career-option";button.role="option";button.dataset.index=String(index);
      const copy=document.createElement("span"),title=document.createElement("span"),meta=document.createElement("small"),score=document.createElement("b");
      title.textContent=career.canonical_title;meta.textContent=`${career.industry} · ${career.sub_industry}`;score.textContent=`${career.ai_augmentation_potential} augment`;
      copy.append(title,meta);button.append(copy,score);button.addEventListener("click",()=>selectCareer(career));button.addEventListener("keydown",event=>{if(event.key==="ArrowDown")optionsFocus(results,index+1);if(event.key==="ArrowUp")optionsFocus(results,index-1);});results.append(button);
    });
    $("#career-search").setAttribute("aria-expanded","true");
  }catch(error){results.replaceChildren();const p=document.createElement("p");p.className="field-hint";p.textContent="Search is temporarily unavailable. You can describe your role below.";results.append(p);}
}
function optionsFocus(root,index){const items=$$(".career-option",root);items[Math.max(0,Math.min(index,items.length-1))]?.focus();}
function closeCareerResults(){$("#career-results").classList.add("hidden");$("#career-search").setAttribute("aria-expanded","false");}
function selectCareer(career){state.selectedCareer=career;$("#career-search").value=career.canonical_title;$("#selected-career").textContent=`Selected: ${career.canonical_title} · ${career.industry}`;$("#selected-career").classList.remove("hidden");$("#industry").value=career.industry;$("#custom-career").value="";$("#custom-career-wrap").classList.add("hidden");closeCareerResults();announce(`${career.canonical_title} selected`);}

$("#email-form")?.addEventListener("submit",async event=>{
  event.preventDefault();
  const input=$("#results-email"),error=$("#email-error"),button=$("#email-form button[type=submit]");
  const email=input.value.trim();
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email)){error.textContent="Enter a valid email address.";input.focus();return;}
  if(!state.assessment?.result){error.textContent="Finish your scan first.";return;}
  error.textContent="";setBusy(button,true,"Sending…");
  try{
    const response=await request(`/profiles/${state.credentials.session_id}/assessments/${state.assessment.assessment_id}/email`,
      {method:"POST",body:JSON.stringify({email,marketing_consent:$("#results-consent").checked})});
    track("results_emailed",{career_id:state.assessment.career.id,consent:$("#results-consent").checked});
    const panel=$(".email-capture");panel.classList.add("done");
    const note=document.createElement("p");note.className="email-sent";
    note.textContent=response?.delivery_enabled===false
      ? `Saved for ${email}. This deployment has email sending switched off, so it will go out once it is connected.`
      : `On its way to ${email}. Check your spam folder if it has not arrived in a few minutes.`;
    panel.append(note);announce(note.textContent);
  }catch(requestError){
    error.textContent=requestError.message||"We could not send that. Try again in a moment.";
  }finally{setBusy(button,false);}
});
$("#profile-form").addEventListener("submit",async event=>{
  event.preventDefault();const button=event.submitter;const first_name=$("#first-name").value.trim();const custom_career=$("#custom-career").value.trim();
  const payload={first_name,career_id:custom_career?"custom-role":state.selectedCareer?.id||null,custom_career:custom_career||null,career_stage:$("#career-stage").value,industry:$("#industry").value,region:$("#region").value.trim()||null,education_level:$("#education").value||null,years_experience:$("#experience").value===""?null:Number($("#experience").value)};
  if(!first_name){return showFormError("Enter your first name.","#first-name");}if(!payload.career_id&&!custom_career){return showFormError("Choose a career or describe your role.","#career-search");}if(!payload.career_stage||!payload.industry){return showFormError("Choose your career stage and industry.","#career-stage");}
  setBusy(button,true,"Securing profile…");
  try{
    if(state.editing&&state.credentials){const data=await request(`/profiles/${state.credentials.session_id}`,{method:"PUT",body:JSON.stringify(payload)});state.profile=data.profile;state.assessment=null;state.editing=false;}
    else{const data=await request("/profiles",{method:"POST",body:JSON.stringify(payload)});storeCredentials({session_id:data.session_id,access_token:data.access_token});state.profile=data.profile;track("onboarding_completed",{career_id:payload.career_id,industry:payload.industry});}
    $("#form-error").textContent="";navigate("avatar");
  }catch(error){showFormError(error.message||"We could not save your profile. Try again.");}finally{setBusy(button,false);}
});
function showFormError(message,selector){$("#form-error").textContent=message;if(selector)$(selector).focus();}
function showCustomCareer(){$("#custom-career-wrap").classList.toggle("hidden");if(!$("#custom-career-wrap").classList.contains("hidden")){state.selectedCareer=null;$("#selected-career").classList.add("hidden");$("#custom-career").focus();track("career_not_found",{query_length:$("#career-search").value.trim().length});}}
function prefillProfile(){if(!state.profile)return;$("#first-name").value=state.profile.first_name||"";$("#career-stage").value=state.profile.career_stage||"";$("#industry").value=state.profile.industry||"";$("#region").value=state.profile.region||"";$("#education").value=state.profile.education_level||"";$("#experience").value=state.profile.years_experience??"";if(state.profile.custom_career){$("#custom-career-wrap").classList.remove("hidden");$("#custom-career").value=state.profile.custom_career;}else if(state.assessment?.career){selectCareer(state.assessment.career);}}

async function openCamera(){
  if(!navigator.mediaDevices?.getUserMedia){$("#camera-status").textContent="Camera is unavailable here. Your champion icon is ready.";return showAvatarDone();}
  try{state.camera=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user",width:{ideal:640},height:{ideal:640}},audio:false});const video=$("#camera-preview");video.srcObject=state.camera;video.classList.remove("hidden");$("#avatar-preview").classList.add("hidden");$("#camera-start-actions").classList.add("hidden");$("#camera-capture-actions").classList.remove("hidden");}
  catch{$("#camera-status").textContent="Camera permission was not granted. Nothing was uploaded.";showAvatarDone();}
}
function capturePhoto(){const video=$("#camera-preview"),canvas=$("#camera-canvas"),ctx=canvas.getContext("2d");ctx.save();ctx.translate(canvas.width,0);ctx.scale(-1,1);ctx.drawImage(video,0,0,canvas.width,canvas.height);ctx.restore();const url=canvas.toDataURL("image/jpeg",.72);sessionStorage.setItem("career-local-photo",url);$("#selfie-image").src=url;$("#selfie-image").classList.remove("hidden");stopCamera();video.classList.add("hidden");$("#avatar-preview").classList.remove("hidden");showAvatarDone();}
function showAvatarDone(){$("#camera-start-actions").classList.add("hidden");$("#camera-capture-actions").classList.add("hidden");$("#camera-done-actions").classList.remove("hidden");}
function retakePhoto(){sessionStorage.removeItem("career-local-photo");$("#selfie-image").classList.add("hidden");$("#avatar-preview").classList.remove("hidden");$("#camera-done-actions").classList.add("hidden");$("#camera-start-actions").classList.remove("hidden");}

async function startAssessment(){
  if(!state.profile||!state.credentials)return navigate("onboarding");
  const button=$("[data-action='start-assessment']");setBusy(button,true,"Building map…");
  try{state.assessment=await request(`/profiles/${state.credentials.session_id}/assessments`,{method:"POST",body:"{}"});state.selectedCareer=state.assessment.career;track("assessment_started",{career_id:state.assessment.career.id,industry:state.assessment.career.industry});renderQuestion();navigate("assessment");}
  catch(error){fail("We could not build your career map. Your profile is saved.",startAssessment);}finally{setBusy(button,false);}
}
function renderQuestion(){
  if(!state.assessment)return;const q=state.assessment.next_question;
  if(!q)return finishAssessment();const progress=state.assessment.progress;
  $("#assessment-greeting").textContent=`${state.profile.first_name}, mapping ${state.assessment.career.canonical_title} through ${progress.total} relevant signals.`;
  $("#question-count").textContent=`Question ${progress.answered+1} of ${progress.total}`;$("#question-construct").textContent=q.construct_id.replaceAll("_"," ");$("#question-text").textContent=q.text;$("#question-why").textContent=q.why_asked;$("#question-progress").style.width=`${progress.percent}%`;$(".question-panel .progress-bar").setAttribute("aria-valuenow",String(progress.percent));$("#assessment-xp").textContent=String(progress.answered*20);
  const stage=Math.min(3,Math.floor(progress.percent/25));$$(".map-node").forEach((node,index)=>{node.classList.toggle("done",index<stage);node.classList.toggle("active",index===stage);});$("#map-line").style.width=`${Math.min(84,progress.percent*.84)}%`;
  const root=$("#answer-options");root.replaceChildren();q.answers.forEach((answer,index)=>{const button=document.createElement("button");button.type="button";button.className="answer-option";button.setAttribute("role","radio");button.setAttribute("aria-checked","false");const key=document.createElement("span");key.textContent=String.fromCharCode(65+index);const text=document.createTextNode(answer.label);button.append(key,text);button.addEventListener("click",()=>submitAnswer(q.id,answer.value,button));root.append(button);});
  $("#assessment-error").textContent="";announce(`Question ${progress.answered+1} of ${progress.total}: ${q.text}`);
}
async function submitAnswer(question_id,answer_index,button){
  $$(".answer-option").forEach(item=>item.disabled=true);button.setAttribute("aria-checked","true");button.classList.add("locked-in");
  try{state.assessment=await request(`/profiles/${state.credentials.session_id}/assessments/${state.assessment.assessment_id}/answers`,{method:"POST",body:JSON.stringify({question_id,answer_index})});announce(`Answer saved. You gained 20 XP, ${state.profile.first_name}.`);setTimeout(renderQuestion,reducedMotion?0:220);}
  catch(error){$("#assessment-error").textContent="Your answer was not saved. Check your connection and try again.";$$(".answer-option").forEach(item=>item.disabled=false);}
}
async function finishAssessment(){
  try{state.assessment=await request(`/profiles/${state.credentials.session_id}/assessments/${state.assessment.assessment_id}/complete`,{method:"POST",body:"{}"});track("assessment_completed",{career_id:state.assessment.career.id});runScan();}
  catch(error){$("#assessment-error").textContent=error.message||"We could not complete the assessment.";}
}

function runScan(){
  navigate("scan");const terminal=$("#terminal");terminal.replaceChildren();$("#scan-title").textContent=`${state.profile.first_name}, your career scan is running`;$("#scan-subtitle").textContent=`Analyzing the tasks behind ${state.assessment.career.canonical_title}.`;$("#scan-skip").classList.remove("hidden");
  const r=state.assessment.result,d=r.dimensions,c=state.assessment.career;
  const lines=[
    "Initializing task-level analysis…",
    `Loading career profile: ${c.canonical_title} [${c.career_family}]`,
    `Career content coverage: ${r.confidence.career_coverage.toUpperCase()}`,
    `Processing ${r.confidence.answered_questions} distinct work signals…`,
    `Automation exposure signal: ${d.automation_exposure}/100`,
    `Human advantage signal: ${d.human_advantage}/100`,
    `Physical-world defensibility: ${d.physical_defensibility}/100`,
    `Accountability protection: ${d.accountability_protection}/100`,
    `AI augmentation opportunity: ${d.augmentation_opportunity}/100`,
    `Career adaptability: ${d.career_adaptability}/100`,
    `ANALYSIS COMPLETE // ${r.overall.status.toUpperCase()}`
  ];let index=0;
  const next=()=>{if(index>=lines.length)return setTimeout(finishScan,reducedMotion?0:550);const div=document.createElement("div");div.textContent=lines[index];if(index===lines.length-1)div.className="bright";if(index===4)div.className="warning";terminal.append(div);terminal.scrollTop=terminal.scrollHeight;index++;const pct=Math.round(index/lines.length*100);$("#scan-progress").style.width=`${pct}%`;$("#scan-percent").textContent=`${pct}%`;state.scanTimer=setTimeout(next,reducedMotion?0:250);};next();
}
async function finishScan(){clearTimeout(state.scanTimer);$("#scan-skip").classList.add("hidden");await gameEvent("scan_completed",{},"scan");renderBattle();navigate("battle");}
function renderBattle(){
  const result=state.assessment.result,pressure=result.overall.transformation_pressure;$("#reel-status").textContent=result.overall.status;$("#reel-pressure").textContent=`${pressure}/100`;$("#reel-confidence").textContent=result.confidence.level;$("#player-label").textContent=state.profile.first_name.toUpperCase();setHP(100-pressure);$("#brace-actions").classList.remove("hidden");$("#skill-combat").classList.add("hidden");$("#results-actions").classList.add("hidden");
  const threats=$("#threat-cards");threats.replaceChildren();result.tasks_most_likely_to_change.slice(0,3).forEach((task,index)=>{const card=document.createElement("article");card.className="threat-card";const n=document.createElement("small"),h=document.createElement("h3"),p=document.createElement("p");n.textContent=`THREAT 0${index+1}`;h.textContent=task;p.textContent="This task may be automated or accelerated; the accountable role is broader than this task.";card.append(n,h,p);threats.append(card);});
}
function setHP(player){player=Math.max(12,Math.min(88,Math.round(player)));$("#player-hp").style.width=`${player}%`;$("#ai-hp").style.width=`${100-player}%`;$("#player-hp-label").textContent=`${player} HP`;$("#ai-hp-label").textContent=`${100-player} HP`;}
async function brace(){await gameEvent("threat_braced",{},"brace");$("#brace-actions").classList.add("hidden");$("#skill-combat").classList.remove("hidden");state.battleIndex=0;renderCombatCard();announce("Impact absorbed. Skill counterattack unlocked.");}
function renderCombatCard(){
  const skills=state.assessment.result.skill_recommendations.slice(0,3),root=$("#combat-card");$("#cards-left").textContent=`${Math.max(0,skills.length-state.battleIndex)} cards`;
  if(state.battleIndex>=skills.length){root.replaceChildren();$("#skill-combat").classList.add("hidden");$("#results-actions").classList.remove("hidden");announce("Counterattack complete. Your strategy is unlocked.");return;}
  const skill=skills[state.battleIndex];root.replaceChildren();const cat=document.createElement("span"),title=document.createElement("h4"),copy=document.createElement("p"),actions=document.createElement("div"),owned=document.createElement("button"),gap=document.createElement("button");cat.className="eyebrow";cat.textContent=skill.category;title.textContent=skill.name;copy.textContent=skill.why;actions.className="button-row";owned.className="button secondary";owned.type="button";owned.textContent="I use this skill";gap.className="button ghost";gap.type="button";gap.textContent="Add to my quest";owned.addEventListener("click",()=>playSkill(skill,"skill_owned"));gap.addEventListener("click",()=>playSkill(skill,"skill_gap"));actions.append(owned,gap);root.append(cat,title,copy,actions);
}
async function playSkill(skill,type){const response=await gameEvent(type,{skill_id:skill.skill_id},`${type}-${skill.skill_id}`);if(response){state.assessment.xp=response.xp;toast(`${type==="skill_owned"?"Skill deployed":"Quest added"} · +${response.xp_delta} XP`);}state.battleIndex++;renderCombatCard();}

function listInto(selector,values){const root=$(selector);root.replaceChildren();values.forEach(value=>{const li=document.createElement("li");li.textContent=value;root.append(li);});}
function rankFor(xp){if(xp>=900)return"Vanguard";if(xp>=650)return"Strategist";if(xp>=400)return"Pathfinder";return"Scout";}
function renderResults(){
  const a=state.assessment,r=a.result,d=r.dimensions,name=state.profile.first_name;$("#results-title").textContent=`${name}, your career scan is ready.`;$("#results-summary").textContent=`As a ${a.career.canonical_title}, ${r.overall.status}. Hand the repetitive parts to AI and spend more of your time where your judgement counts.`;$("#confidence-chip").textContent=`${r.confidence.level} detail on this job`;$("#xp-total").textContent=`${a.xp} XP`;$("#rank-name").textContent=rankFor(a.xp);
  const labels={automation_exposure:"How much of your work AI can already do",augmentation_opportunity:"How much AI could speed you up",human_advantage:"Work that still needs a person",physical_defensibility:"Hands-on work in the real world",accountability_protection:"Decisions someone must answer for",reskilling_urgency:"How soon to start learning",career_adaptability:"How easily you can adapt"};const grid=$("#dimension-grid");grid.replaceChildren();Object.entries(d).forEach(([key,value])=>{const card=document.createElement("article");card.className="dimension-card";const label=document.createElement("span"),score=document.createElement("strong"),meter=document.createElement("div"),fill=document.createElement("i");label.textContent=labels[key]||key;score.textContent=`${value}/100`;meter.className="meter";fill.style.width=`${value}%`;meter.append(fill);card.append(label,score,meter);grid.append(card);});
  listInto("#change-tasks",r.tasks_most_likely_to_change);listInto("#durable-tasks",r.tasks_least_likely_to_be_automated);const influences=$("#influence-list");influences.replaceChildren();r.top_answer_influences.forEach(item=>{const row=document.createElement("article"),copy=document.createElement("div"),answer=document.createElement("strong"),why=document.createElement("p"),badge=document.createElement("b");row.className="influence";answer.textContent=item.answer;why.textContent=item.explanation;badge.textContent=CONSTRUCT_LABELS[item.construct_id]||item.construct_id.replaceAll("_"," ");copy.append(answer,why);row.append(copy,badge);influences.append(row);});
  const skills=$("#skill-grid");skills.replaceChildren();r.skill_recommendations.forEach(skill=>skills.append(skillCard(skill)));$("#future-copy").textContent=`Start with ${r.skill_recommendations[0]?.name||"one focused skill"}. Let AI handle the repetitive work, then aim for roles like ${r.emerging_opportunities.join(", ")}. Related jobs worth a look: ${r.adjacent_career_paths.join(", ")}.`;
}
function skillCard(skill){
  const active=startedQuests().includes(skill.skill_id);
  const card=document.createElement("article");card.className=active?"skill-card started":"skill-card";
  const head=document.createElement("div");head.className="skill-head";
  const category=document.createElement("span");category.className="category";category.textContent=skill.category;
  const badge=document.createElement("span");badge.className="quest-badge";badge.textContent="In progress";
  head.append(category,badge);
  const title=document.createElement("h4");title.textContent=skill.name;
  const why=document.createElement("p");why.textContent=skill.why;
  const meta=document.createElement("div");meta.className="skill-meta";
  for(const text of [skill.difficulty,skill.time_to_develop,`+${skill.xp_reward} XP`]){const chip=document.createElement("span");chip.textContent=text;meta.append(chip);}
  const details=document.createElement("details");details.open=active;
  const summary=document.createElement("summary");summary.textContent="Show the plan";
  const action=document.createElement("p");action.className="first-action";action.textContent=`Start here: ${skill.first_action}`;
  details.append(summary,action);
  if(Array.isArray(skill.learning_pathway)&&skill.learning_pathway.length){
    const heading=document.createElement("p");heading.className="pathway-heading";heading.textContent="Then work through";
    const pathway=document.createElement("ol");pathway.className="quest-pathway";
    for(const step of skill.learning_pathway){const item=document.createElement("li");item.textContent=step;pathway.append(item);}
    details.append(heading,pathway);
  }
  const button=document.createElement("button");button.type="button";button.className="button ghost wide";
  const paint=on=>{card.classList.toggle("started",on);button.textContent=on?"Quest in progress":"Start this quest";button.classList.toggle("ghost",!on);button.classList.toggle("secondary",on);button.disabled=on;};
  paint(active);
  button.addEventListener("click",async()=>{
    setBusy(button,true,"Starting…");
    const response=await gameEvent("action_started",{skill_id:skill.skill_id},`action-${skill.skill_id}`);
    setBusy(button,false);
    if(!response){toast("We could not start that quest. Check your connection and try again.");return;}
    track("action_plan_started",{skill_id:skill.skill_id,career_id:state.assessment.career.id});
    rememberQuest(skill.skill_id);
    details.open=true;paint(true);
    state.assessment.xp=response.xp;$("#xp-total").textContent=`${response.xp} XP`;$("#rank-name").textContent=rankFor(response.xp);
    toast(response.awarded?`${skill.name} started · +${response.xp_delta} XP`:`${skill.name} is already in progress`);
    announce(`${skill.name} added to your active quests. First step: ${skill.first_action}`);
  });
  details.addEventListener("toggle",()=>{if(details.open)track("skill_card_opened",{skill_id:skill.skill_id,career_id:state.assessment.career.id});});
  card.append(head,title,why,meta,details,button);return card;
}
async function viewResults(){renderResults();navigate("results");track("result_viewed",{screen:"results",career_id:state.assessment.career.id});}

async function editProfile(){if(!state.profile)return navigate("onboarding");state.editing=true;prefillProfile();navigate("onboarding");}
async function restart(){if(!state.profile)return navigate("onboarding");state.assessment=null;sessionStorage.removeItem("career-local-photo");navigate("avatar");toast("New mission ready. Your profile was kept.");}
async function deleteProgress(){
  if(!state.credentials)return;
  if(!confirm("Delete your saved profile, answers, results, and XP from this browser session? This cannot be undone."))return;
  try{await request(`/profiles/${state.credentials.session_id}`,{method:"DELETE"});}catch{toast("Could not confirm deletion. Try again.");return;}
  storeCredentials(null);sessionStorage.removeItem("career-local-photo");localStorage.removeItem(QUEST_KEY);Object.assign(state,{profile:null,assessment:null,selectedCareer:null,editing:false});$("#resume-button").classList.add("hidden");$("#profile-form").reset();navigate("landing");toast("Saved profile and progress deleted.");
}

document.addEventListener("click",event=>{
  const action=event.target.closest("[data-action]")?.dataset.action;if(!action)return;
  const actions={home:()=>navigate("landing"),begin:()=>{track("onboarding_started",{screen:"landing"});navigate("onboarding");},resume,customCareer:showCustomCareer,"custom-career":showCustomCareer,"open-camera":openCamera,"capture-photo":capturePhoto,"retake-photo":retakePhoto,"skip-avatar":showAvatarDone,"start-assessment":startAssessment,"finish-scan":finishScan,brace,"view-results":viewResults,restart,"edit-profile":editProfile,"delete-progress":deleteProgress,retry:()=>state.retry?.()};
  actions[action]?.();
});
function routeFromLocation(fallback){const name=fallback||location.hash.replace("#/","")||"landing";return ROUTES.includes(name)?name:"landing";}
window.addEventListener("popstate",event=>navigate(routeFromLocation(event.state?.screen),false));
window.addEventListener("hashchange",()=>{const name=routeFromLocation();if(!$(`#screen-${name}`)?.classList.contains("active"))navigate(name,false);});
window.addEventListener("offline",()=>toast("You are offline. Saved progress will remain available after reconnecting."));
document.addEventListener("visibilitychange",()=>{if(document.hidden&&location.hash==="#/assessment"&&state.assessment?.next_question)track("question_abandoned",{question_id:state.assessment.next_question.id,screen:"assessment"});});
document.addEventListener("keydown",event=>{
  if(location.hash!=="#/assessment"||event.altKey||event.ctrlKey||event.metaKey)return;
  const index=["a","b","c","d","e"].indexOf(event.key.toLowerCase());
  const option=index>=0?$$(".answer-option")[index]:null;
  if(option&&!option.disabled){event.preventDefault();option.click();}
});
boot();
