
const elExpr = document.getElementById("expression");
const elHist = document.getElementById("history");
const keys = document.querySelectorAll(".key");
const aiOverlay = document.getElementById("aiOverlay");
const aiSheet = document.getElementById("aiSheet");
const aiOpen = document.getElementById("aiOpen");
const aiClose = document.getElementById("aiClose");
const themeToggle = document.getElementById("themeToggle");
const aiInput = document.getElementById("aiInput");
const aiSolve = document.getElementById("aiSolve");
const aiOutput = document.getElementById("aiOutput");

let expr = "";
let justEvaluated = false;

function render(){
  elExpr.textContent = expr || "0";
}

function append(v){
  if(justEvaluated && /[0-9.]/.test(v)){
    expr = "";
  }
  justEvaluated = false;
  expr += v;
  render();
}

function clearAll(){
  expr = "";
  elHist.textContent = "";
  render();
}

function backspace(){
  expr = expr.slice(0, -1);
  render();
}

function normalizeForServer(s){
  return s
    .replace(/×/g,"*")
    .replace(/÷/g,"/")
    .replace(/−/g,"-")
    .replace(/:/g,"/"); // ✅ allow 10:3
}

async function postJSON(url, data){
  const r = await fetch(url, {
    method:"POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(data)
  });
  return await r.json();
}

async function evaluate(){
  if(!expr.trim()) return;
  const raw = expr;
  const serverExpr = normalizeForServer(raw);
  const res = await postJSON("/api/calc", {expression: serverExpr});
  if(res.error){
    elHist.textContent = raw;
    expr = "Ошибка";
  }else{
    elHist.textContent = raw + " =";
    expr = res.result;
  }
  justEvaluated = true;
  render();
}

keys.forEach(k=>{
  k.addEventListener("click", ()=>{
    const act = k.dataset.action;
    const val = k.dataset.value;
    if(act==="clear") return clearAll();
    if(act==="back") return backspace();
    if(act==="equals") return evaluate();
    if(val){
      if(val==="." ){
        const last = expr.split(/[\+\-\*\/\^\(\)]/).pop();
        if(last.includes(".")) return;
      }
      append(val);
    }
  })
});

function openAI(){
  aiOverlay.classList.remove("hidden");
  aiOverlay.setAttribute("aria-hidden","false");
  aiInput.value = normalizeForServer(expr || "");
  aiInput.focus();
}

function closeAI(){
  aiOverlay.classList.add("hidden");
  aiOverlay.setAttribute("aria-hidden","true");
  aiOutput.innerHTML = "";
}

aiOpen.addEventListener("click", openAI);
aiClose.addEventListener("click", closeAI);

// ======= Fix #2: don't close on selection drag =======
let overlayDownOutside = false;

aiOverlay.addEventListener("mousedown", (e)=>{
  overlayDownOutside = (e.target === aiOverlay);
});

aiOverlay.addEventListener("mouseup", (e)=>{
  // close only if press+release happened on overlay itself (true click outside)
  if(overlayDownOutside && e.target === aiOverlay){
    const sel = window.getSelection ? window.getSelection().toString() : "";
    if(sel) return; // if user selected text, don't close
    closeAI();
  }
  overlayDownOutside = false;
});

// stop bubbling just in case
aiSheet.addEventListener("mousedown", (e)=> e.stopPropagation());
aiSheet.addEventListener("mouseup", (e)=> e.stopPropagation());
aiSheet.addEventListener("click", (e)=> e.stopPropagation());

themeToggle.addEventListener("click", ()=>{
  document.body.classList.toggle("light");
});

aiSolve.addEventListener("click", async ()=>{
  const q = aiInput.value.trim();
  if(!q){
    aiOutput.innerHTML = "<div class='step error'>Введи пример или текстовый запрос.</div>";
    return;
  }
  aiOutput.innerHTML = "<div class='step'>Думаю…</div>";
  const res = await postJSON("/api/assist", {expression: q});
  if(res.error){
    aiOutput.innerHTML = `<div class='step error'>${res.error}</div>`;
    return;
  }
  const steps = res.steps || [];
  aiOutput.innerHTML = steps.map(s=>`<div class='step'>${escapeHTML(s)}</div>`).join("") +
    `<div class='step final'>Ответ: ${escapeHTML(res.result)}</div>`;
});

function escapeHTML(str){
  return (str+"").replace(/[&<>"']/g, s=>({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[s]));
}

// keyboard support for calculator, но не мешаем полям ввода и учитываем AI overlay
window.addEventListener("keydown", (e)=>{
  const active = document.activeElement;
  const tag = active && active.tagName ? active.tagName.toLowerCase() : "";
  const isTyping = tag === "input" || tag === "textarea" || (active && active.isContentEditable);

  if(isTyping) return;

  // если AI открыт — Esc закрывает его
  if(!aiOverlay.classList.contains("hidden") && e.key === "Escape"){
    e.preventDefault();
    closeAI();
    return;
  }

  const k = e.key;
  if(k==="Enter") {
    e.preventDefault();
    evaluate();
  }
  else if(k==="Backspace") {
    e.preventDefault();
    backspace();
  }
  else if(k==="Escape") {
    e.preventDefault();
    clearAll();
  }
  else if(/[0-9\.\+\-\*\/\(\)\^:]/.test(k)) { // allow :
    append(k);
  }
});
