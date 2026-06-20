const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const j = async (u, o) => (await fetch(u, o)).json();

/* ---- accessibility: text size + contrast (remembered) ---- */
let fs = parseInt(localStorage.getItem("ld_fs") || "19");
const applyFs = () => { document.documentElement.style.setProperty("--fs", fs + "px"); localStorage.setItem("ld_fs", fs); };
$("#bigger").onclick = () => { fs = Math.min(28, fs + 2); applyFs(); };
$("#smaller").onclick = () => { fs = Math.max(15, fs - 2); applyFs(); };
applyFs();
if (localStorage.getItem("ld_contrast") === "1") document.body.classList.add("contrast");
$("#contrast").onclick = () => { document.body.classList.toggle("contrast"); localStorage.setItem("ld_contrast", document.body.classList.contains("contrast") ? "1" : "0"); };

/* ---- tabs ---- */
document.querySelectorAll(".bigtabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".bigtabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("hide", t.id !== b.dataset.tab));
  if (b.dataset.tab === "proof") loadReceipts();
  if (b.dataset.tab === "vault") loadSections();
  window.scrollTo(0, 0);
});

/* ---- tiny markdown -> html (headers, bold, lists, tables, hr) ---- */
function md(src) {
  const lines = src.split("\n"); let html = "", i = 0;
  const inline = t => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
  while (i < lines.length) {
    let l = lines[i];
    if (/^#{1,3}\s/.test(l)) { const n = l.match(/^#+/)[0].length; html += `<h${n}>${inline(l.replace(/^#+\s/, ""))}</h${n}>`; i++; continue; }
    if (/^---+\s*$/.test(l)) { html += "<hr>"; i++; continue; }
    if (/^\s*[-*]\s/.test(l)) { html += "<ul>"; while (i < lines.length && /^\s*[-*]\s/.test(lines[i])) { html += `<li>${inline(lines[i].replace(/^\s*[-*]\s/, ""))}</li>`; i++; } html += "</ul>"; continue; }
    if (/^\|.*\|/.test(l)) {
      const rows = []; while (i < lines.length && /^\|.*\|/.test(lines[i])) { rows.push(lines[i]); i++; }
      const cells = r => r.split("|").slice(1, -1).map(c => c.trim());
      html += "<table>";
      rows.forEach((r, ri) => { if (/^\|[\s:|-]+\|$/.test(r)) return; const tag = ri === 0 ? "th" : "td";
        html += "<tr>" + cells(r).map(c => `<${tag}>${inline(c)}</${tag}>`).join("") + "</tr>"; });
      html += "</table>"; continue;
    }
    if (l.trim() === "") { i++; continue; }
    html += `<p>${inline(l)}</p>`; i++;
  }
  return html;
}

/* ---- Today ---- */
const catIcon = c => ({medication:"💊", care:"👣", supplies:"🛒", appointment:"📅"}[c] || "🐝");
async function loadToday() {
  const d = await j("/api/today");
  $("#hello").textContent = "· " + d.date;
  $("#todayhead").textContent = "Today — " + d.date;
  const due = d.reminders.filter(r => r.needs_ack || r.escalated);
  const rest = d.reminders.filter(r => !r.needs_ack && !r.escalated);
  const card = r => `<div class="rcard ${r.escalated?'esc':r.needs_ack?'due':''}">
      <div><div class="tag">${esc(r.category)}</div>
        <div class="t">${catIcon(r.category)} ${esc(r.title)}</div>
        <div class="n">${esc(r.nudge)}</div>
        ${r.escalated?'<div class="n">⚠️ A family member was checked in with.</div>':''}
        ${r.vault_ref?`<div class="ref">▸ ${esc(r.vault_ref)}</div>`:''}</div>
      ${r.needs_ack?`<button class="ackbtn" data-id="${esc(r.id)}">✓ I did it</button>`:`<div class="muted">${esc(r.schedule)}</div>`}
    </div>`;
  $("#reminders").innerHTML =
    (due.length ? `<h2>Needs you now</h2>` + due.map(card).join("") : `<p class="muted">Nothing needs you right now — nicely done. 🐝</p>`) +
    `<h2 style="margin-top:22px">Your reminders</h2>` + rest.map(card).join("");
  document.querySelectorAll(".ackbtn").forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = "Saved ✓";
    await fetch("/api/ack", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id:b.dataset.id})});
    loadToday();
  });
}

/* ---- Vault ---- */
async function loadSections() {
  if ($("#sections").dataset.loaded) return;
  const {sections} = await j("/api/sections");
  $("#sections").innerHTML = sections.map(s => `<button class="sec" data-key="${s.key}"><span class="ic">${s.icon}</span>${esc(s.title)}</button>`).join("");
  $("#sections").dataset.loaded = "1";
  document.querySelectorAll(".sec").forEach(b => b.onclick = () => openSection(b.dataset.key));
}
async function openSection(key) {
  const s = await j("/api/section?key=" + encodeURIComponent(key));
  $("#viewerBody").innerHTML = `<h1>${s.icon} ${esc(s.title)}</h1>` + (s.text ? md(s.text) : "<p class='muted'>This is empty so far. You can fill it in on your box.</p>");
  $("#viewer").classList.remove("hide"); $("#sections").classList.add("hide");
  window.scrollTo(0, 0);
}
$("#closeView").onclick = () => { $("#viewer").classList.add("hide"); $("#sections").classList.remove("hide"); };

/* ---- Helper ---- */
$("#askForm").onsubmit = async e => {
  e.preventDefault(); const f = e.target, n = $("#askNote"), out = $("#askOut");
  n.className = "note"; n.textContent = "Thinking on your box… (this can take a moment)"; out.classList.add("hide");
  try {
    const r = await j("/api/ask", {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({doctor:f.doctor.value, reason:f.reason.value})});
    if (r.ok){ n.className="note ok"; n.textContent="Ready — saved to your vault. Confirm anything medical with your clinician.";
      out.textContent = r.text; out.classList.remove("hide"); }
    else { n.className="note bad"; n.textContent = r.error || "The helper is resting — try again in a moment."; }
  } catch { n.className="note bad"; n.textContent="The helper is resting — try again in a moment."; }
};

/* ---- Care pack ---- */
$("#careForm").onsubmit = async e => {
  e.preventDefault(); const f = e.target, n = $("#careNote");
  n.className = "note"; n.textContent = "Sending…";
  try {
    const r = await j("/api/carepack", {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({need:f.need.value, details:f.details.value})});
    if (r.ok){ n.className="note ok"; n.textContent = r.note; f.reset(); }
    else { n.className="note bad"; n.textContent = r.error || "Could not save — try again."; }
  } catch { n.className="note bad"; n.textContent="Could not save — try again."; }
};

/* ---- Receipts ---- */
async function loadReceipts() {
  const {receipts} = await j("/api/receipts");
  const tag = r => (r.kind === "reminder-fired" && r.left_premises)
    ? `<div class="tag" style="color:var(--blue)">📱 sent to your phone · no records</div>`
    : (r.left_premises
        ? `<div class="tag" style="color:var(--blue)">📱 generic nudge · no records</div>`
        : `<div class="tag" style="color:var(--green)">🔒 stayed on your box ✓</div>`);
  $("#receipts").innerHTML = receipts.length ? receipts.map(r => `<div class="rcard">
      <div><div class="t" style="font-size:1.02rem">${esc(r.what)}</div><div class="muted">${esc(r.when)}</div></div>
      ${tag(r)}</div>`).join("") : `<p class="muted">No activity yet.</p>`;
}

loadToday();
setInterval(loadToday, 30000);
