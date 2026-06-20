#!/usr/bin/env python3
"""
LocalDiabetic Dashboard — the member's home screen (HAT 2 surface)
==================================================================

A tiny, offline-capable web app served FROM the member's own box. It reads the
real vault, the live reminder engine, and the receipts, and lets the member run
their diabetic life from one warm, accessible screen — Today, foot care, meds,
appointments, supplies, family, the on-box helper, care-packs, the emergency card.

THE FIREWALL HOLDS. Everything here is local: the dashboard reads the member's
own files on the member's own box and never calls out. The on-box helper runs on
the local edge model. Records never leave home. Every action that does anything
mints a receipt.

  python3 ld_dashboard.py --port 8080 [--model-host http://192.168.0.79:11434]

Stdlib only. Bind to localhost (or the LAN) on the member's box.
"""

import argparse
import json
import mimetypes
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))   # the vault root
DASH = os.path.join(HERE, "dashboard")
RECEIPTS = os.path.join(HERE, "14-receipts")
sys.path.insert(0, os.path.join(HERE, "engine"))
sys.path.insert(0, os.path.join(HERE, "helper"))
import ld_remind  # the live engine (reminders + state + ack)
try:
    import ld_helper  # the on-box helper (HAT 2)
except Exception:
    ld_helper = None

MODEL_HOST = "http://127.0.0.1:11434"
MODEL_NAME = "hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M"

# vault sections the dashboard surfaces (prefer the member's filled-in -MINE copy)
SECTIONS = [
    ("emergency", "Emergency card", "00-emergency-card/EMERGENCY-CARD.md", "🚨"),
    ("meds", "My medications", "01-medications/MEDICATION-LIST.md", "💊"),
    ("doctors", "Doctors & pharmacy", "02-doctors-pharmacy/CONTACTS.md", "📞"),
    ("foot", "Foot care", "06-foot-care/FOOT-CHECK-CHECKLIST.md", "👣"),
    ("appts", "Appointments", "10-appointments/APPOINTMENT-PREP.md", "📅"),
    ("supplies", "Supplies", "08-supplies/SUPPLY-INVENTORY.md", "🛒"),
    ("food", "Food & shopping", "09-food-cookbooks/FOOD-PLAN.md", "🍎"),
    ("family", "Family & helpers", "11-family-helpers/HELPERS.md", "🤝"),
]


def _read(rel):
    for cand in (rel.replace(".md", "-MINE.md"), rel):
        p = os.path.join(HERE, cand)
        if os.path.isfile(p):
            return open(p, encoding="utf-8").read(), cand
    return "", rel


def today():
    reminders, _ = ld_remind.load_config(ld_remind.DEFAULT_CONFIG)
    state = ld_remind.load_state()
    now = datetime.now()
    out = []
    for r in reminders:
        st = state.get(r["id"], {})
        pending = st.get("pending")
        out.append({
            "id": r["id"], "title": r.get("title", r["id"]), "nudge": r.get("nudge", ""),
            "category": r.get("category", "care"), "schedule": r.get("schedule", ""),
            "vault_ref": r.get("vault_ref", ""),
            "needs_ack": bool(pending and not pending.get("escalated")),
            "escalated": bool(pending and pending.get("escalated")),
        })
    return {"date": now.strftime("%A, %B %-d"), "time": now.strftime("%-I:%M %p"), "reminders": out}


def receipts(limit=25):
    if not os.path.isdir(RECEIPTS):
        return []
    out = []
    for fn in sorted(os.listdir(RECEIPTS), reverse=True):
        if not fn.endswith(".json"):
            continue
        try:
            r = json.load(open(os.path.join(RECEIPTS, fn), encoding="utf-8"))
        except Exception:
            continue
        kind = r.get("kind", "")
        when = r.get("fired_at") or r.get("created_at") or r.get("acknowledged_at") or r.get("escalated_at") or ""
        if kind == "reminder-fired":
            what = f"Reminder: {r.get('title','')}"
        elif kind == "reminder-acknowledged":
            what = f"✓ You acknowledged {r.get('reminder_id','')}"
        elif kind == "reminder-escalated":
            what = f"⚠️ Family check-in sent: {r.get('reminder_id','')}"
        elif kind == "helper-organize":
            what = f"Helper organized: {r.get('title','')}"
        elif kind == "care-pack-request":
            what = f"Care-pack requested: {r.get('need','')}"
        else:
            what = kind
        out.append({"what": what, "when": when, "kind": kind,
                    "left_premises": r.get("left_the_vault", r.get("left_premises", False))})
        if len(out) >= limit:
            break
    return out


def mint(kind, payload):
    os.makedirs(RECEIPTS, exist_ok=True)
    rec = {"kind": kind, "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
           "left_premises": False, "called_hive": False, **payload}
    fn = f"{kind}-{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    json.dump(rec, open(os.path.join(RECEIPTS, fn), "w", encoding="utf-8"), indent=2)
    return rec


# ── Life events (the timeline) — fed by Home Assistant + manual notes ────────
STATE = os.path.join(HERE, ".state")
LIFE_LOG = os.path.join(STATE, "life_events.jsonl")
# the only types we accept (keeps the firewall + the UI clean)
EVENT_TYPES = {"fridge", "help", "meds", "foot", "glucose", "safety", "device",
               "note", "mood", "milestone", "appointment", "supply"}


def log_event(etype, title, message="", severity="info", source="dashboard"):
    os.makedirs(STATE, exist_ok=True)
    ev = {"type": etype if etype in EVENT_TYPES else "note",
          "title": (title or "")[:140], "message": (message or "")[:400],
          "severity": severity if severity in ("info", "good", "warn", "alert") else "info",
          "source": source, "at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
    with open(LIFE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev) + "\n")
    mint("life-event", ev)   # also leaves an on-box receipt
    return ev


def life_events(limit=40):
    out = []
    if os.path.exists(LIFE_LOG):
        for line in reversed(open(LIFE_LOG, encoding="utf-8").read().splitlines()):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
            if len(out) >= limit:
                break
    return out


def notify_generic(message):
    """Fire a GENERIC off-box push for an alert. Refuses anything that scans as PHI."""
    url = os.environ.get("LD_WEBHOOK_URL")
    if not url:
        try:
            for r in json.load(open(ld_remind.DEFAULT_CONFIG)).get("reminders", []):
                if r.get("webhook_url"):
                    url = r["webhook_url"]
                    break
        except Exception:
            pass
    if not url or ld_remind.scan_phi(message):   # firewall: never push PHI off-box
        return False
    try:
        return ld_remind.post_webhook(url, message, title="LocalDiabetic")
    except Exception:
        return False


class Dash(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(DASH, rel))
        if not full.startswith(DASH) or not os.path.isfile(full):
            return self._json({"error": "not found"}, 404)
        data = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(full)[0] or "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/today":
            return self._json(today())
        if u.path == "/api/sections":
            return self._json({"sections": [{"key": k, "title": t, "icon": i} for k, t, _, i in SECTIONS]})
        if u.path == "/api/section":
            key = parse_qs(u.query).get("key", [""])[0]
            m = next((s for s in SECTIONS if s[0] == key), None)
            if not m:
                return self._json({"error": "unknown section"}, 404)
            text, used = _read(m[2])
            return self._json({"key": key, "title": m[1], "icon": m[3], "file": used, "text": text})
        if u.path == "/api/receipts":
            return self._json({"receipts": receipts()})
        if u.path == "/api/events":
            return self._json({"events": life_events()})
        return self._static(u.path)

    def do_POST(self):
        u = urlparse(self.path)

        # Home Assistant (and any local source) posts a life event here.
        # Optional shared token: if LD_EVENT_TOKEN is set, require header X-LD-Token.
        if u.path == "/api/event":
            tok = os.environ.get("LD_EVENT_TOKEN")
            if tok and self.headers.get("X-LD-Token") != tok:
                return self._json({"error": "unauthorized"}, 401)
            b = self._body()
            ev = log_event(b.get("type", "device"), b.get("title", ""), b.get("message", ""),
                           b.get("severity", "info"), b.get("source", "home-assistant"))
            pushed = False
            # an alert can also fire a GENERIC off-box nudge (firewall-checked)
            if b.get("notify") and ev["severity"] in ("warn", "alert"):
                pushed = notify_generic(b.get("nudge") or ev["title"])
            return self._json({"ok": True, "event": ev, "pushed": pushed})

        if u.path == "/api/ack":
            b = self._body()
            rid = b.get("id", "")
            ld_remind.acknowledge(rid, b.get("by", "me"), datetime.now())
            log_event("meds" if "med" in rid else "note", "Done ✓", f"Acknowledged: {rid}", "good", "dashboard")
            return self._json({"ok": True})
        if u.path == "/api/carepack":
            b = self._body()
            need = (b.get("need") or "")[:80]
            details = (b.get("details") or "")[:500]
            line = f"\n- [{datetime.now().strftime('%Y-%m-%d %H:%M')}] {need} — {details}\n"
            cp = os.path.join(HERE, "12-care-packs", "MY-REQUESTS-MINE.md")
            os.makedirs(os.path.dirname(cp), exist_ok=True)
            open(cp, "a", encoding="utf-8").write(line)
            mint("care-pack-request", {"need": need, "details": details, "status": "requested"})
            log_event("supply", "Care-pack requested", need, "info", "dashboard")
            return self._json({"ok": True, "note": "Request saved on your box. We'll reach out as we open our doors."})
        if u.path == "/api/ask":
            if ld_helper is None:
                return self._json({"error": "helper not available"}, 503)
            b = self._body()
            doctor = (b.get("doctor") or "your doctor")[:80]
            reason = (b.get("reason") or "appointment")[:120]
            prompt = (f"A person with diabetes has an appointment: {reason}, with {doctor}. "
                      "Write a short, plain-language checklist of practical QUESTIONS they should ask the "
                      "doctor, plus what to bring. Do not answer them, do not diagnose. 6-9 bullet points.")
            try:
                body, secs = ld_helper.call_model(MODEL_HOST, MODEL_NAME, prompt)
            except Exception as e:
                return self._json({"error": f"the helper is resting: {e}"}, 503)
            note, receipt, flags = ld_helper.write_note(
                HERE, "prep-appointment", f"Questions for {doctor}", body, MODEL_NAME, MODEL_HOST, secs,
                ["10-appointments/APPOINTMENT-PREP.md"])
            return self._json({"ok": True, "text": body, "diagnosis_flags": flags})
        return self._json({"error": "not found"}, 404)


def main():
    global MODEL_HOST, MODEL_NAME
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--model-host", default=MODEL_HOST)
    p.add_argument("--model", default=MODEL_NAME)
    a = p.parse_args()
    MODEL_HOST, MODEL_NAME = a.model_host, a.model
    print(f"LocalDiabetic dashboard on {a.bind}:{a.port}  (vault: {HERE})")
    ThreadingHTTPServer((a.bind, a.port), Dash).serve_forever()


if __name__ == "__main__":
    main()
