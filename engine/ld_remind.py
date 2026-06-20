#!/usr/bin/env python3
"""
LocalDiabetic Reminder Engine — "the Nudge"
===========================================

The second half of the box: Vault + Nudge.

Fires gentle, on-time reminders — foot check, medications, supply reorders,
appointments — to the local box and (optionally) to a phone/watch over a
bridge you own. If a reminder isn't acknowledged in time, it escalates to a
family helper so no one living alone falls through the cracks.

THE INVARIANT, ENFORCED STRUCTURALLY
------------------------------------
This engine NEVER reads the contents of a record. It only ever emits the
generic `nudge` string the user declared in reminders.json. The medical
detail (which med, which dose, which wound) stays in the vault as a pointer
(`vault_ref`) the user follows ON THE BOX. PHI cannot leak because the engine
never loads PHI in the first place.

Off-box channels (a webhook to your phone, or a family helper's phone) carry
ONLY declared generic text. Local channels (console, on-box log) may show the
title and pointer.

ACK + ESCALATION (the safety net)
---------------------------------
A reminder may declare an `escalate` block. When it fires it becomes "pending
ack" with a deadline. The person (or a future tap-to-ack UI / a helper) runs:
    python3 ld_remind.py --ack <id>
If the deadline passes with no ack, the engine notifies the named family
helper(s) with a generic check-in message — never medical detail.

RECEIPTS
--------
Every fire, every ack, every escalation mints a receipt into ../14-receipts/
proving what happened, whether anything left the vault, and that no diagnosis
was given.

FAIL OPEN
---------
Every channel is isolated so a failure NEVER blocks the others. The local log
is the always-works rail — a dead phone bridge can never stop the foot-check
from landing on the box, nor stop a helper escalation from being logged.

USAGE
-----
    python3 ld_remind.py                 # one tick: escalate overdue, fire due
    python3 ld_remind.py --dry-run       # show what WOULD happen, change nothing
    python3 ld_remind.py --at 2026-06-20T08:00   # simulate a time (testing)
    python3 ld_remind.py --ack foot-check [--by jane]   # acknowledge a reminder
    python3 ld_remind.py --pending       # show what's awaiting ack / escalated
    python3 ld_remind.py --list          # list configured reminders
    python3 ld_remind.py --config path   # use a different config

Run it once a minute from cron / a systemd timer / a Synology Scheduled Task.
See README.md for install recipes. Stdlib only — no pip install required.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta

# ── Paths ────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_ROOT = os.path.dirname(HERE)  # the vault folders live one level up
DEFAULT_CONFIG = os.path.join(HERE, "reminders.json")
STATE_DIR = os.path.join(HERE, ".state")
STATE_FILE = os.path.join(STATE_DIR, "last_fired.json")
LOCAL_LOG = os.path.join(STATE_DIR, "notifications.log")
RECEIPTS_DIR = os.path.join(VAULT_ROOT, "14-receipts")

WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

# Off-box channels carry only declared generic text — never title/detail.
OFF_BOX_CHANNELS = {"webhook", "email"}

# A backstop scan. The real protection is that the engine never loads PHI;
# this just flags an author who accidentally put detail in a generic message.
PHI_HINTS = [
    "insulin", "units", "mg", "ml", "dose", "glucose", "a1c", "bp ",
    "blood pressure", "metformin", "lantus", "humalog", "novolog",
    "diagnosis", "wound", "ulcer", "mmol", "mg/dl",
]


# ── Config & state ───────────────────────────────────────────────────────────
def load_config(path):
    if not os.path.exists(path):
        sys.exit(
            f"No config at {path}\n"
            f"Copy reminders.example.json -> reminders.json and edit it."
        )
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("reminders", []), cfg.get("helpers", [])


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def local_log(line):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(LOCAL_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass  # the on-box log itself fails open


# ── Schedule parsing & due logic ─────────────────────────────────────────────
def parse_hhmm(s):
    h, m = s.split(":")
    return int(h), int(m)


def occurrence_for(reminder, now):
    """
    Return (is_due, occurrence_key) for a reminder at time `now`.

    Supported schedules:
      daily@HH:MM
      weekly@DAY[,DAY]@HH:MM        (DAY in MON..SUN)
      interval_days@N@HH:MM         (every N days, based on last fire date)
      once@YYYY-MM-DD@HH:MM         (one-shot: appointment, refill-by)
    """
    sched = reminder["schedule"]
    grace = timedelta(hours=reminder.get("grace_hours", 12))
    parts = sched.split("@")
    kind = parts[0]

    if kind == "daily":
        h, m = parse_hhmm(parts[1])
        due = now.replace(hour=h, minute=m, second=0, microsecond=0)
        key = due.strftime("%Y-%m-%dT%H:%M")
        return (due <= now <= due + grace, key)

    if kind == "weekly":
        days = [d.strip().upper() for d in parts[1].split(",")]
        h, m = parse_hhmm(parts[2])
        if WEEKDAYS[now.weekday()] not in days:
            return (False, None)
        due = now.replace(hour=h, minute=m, second=0, microsecond=0)
        key = due.strftime("%Y-%m-%dT%H:%M")
        return (due <= now <= due + grace, key)

    if kind == "interval_days":
        n = int(parts[1])
        h, m = parse_hhmm(parts[2])
        due = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now < due or now > due + grace:
            return (False, None)
        last = reminder.get("_last_fire_date")
        if last:
            last_d = datetime.strptime(last, "%Y-%m-%d").date()
            if (now.date() - last_d).days < n:
                return (False, None)
        return (True, now.strftime("%Y-%m-%d"))

    if kind == "once":
        due = datetime.strptime(parts[1] + " " + parts[2], "%Y-%m-%d %H:%M")
        key = due.strftime("%Y-%m-%dT%H:%M")
        return (due <= now <= due + grace, key)

    sys.stderr.write(f"[warn] reminder {reminder.get('id')}: unknown schedule '{sched}'\n")
    return (False, None)


# ── PHI guard ────────────────────────────────────────────────────────────────
def scan_phi(text):
    low = (text or "").lower()
    return [h.strip() for h in PHI_HINTS if h in low]


# ── Low-level delivery (fails open at the caller) ────────────────────────────
def post_webhook(url, payload, title="LocalDiabetic"):
    """POST a plain-text payload to an off-box bridge. Caller handles failure."""
    data = payload.encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    # HTTP headers are latin-1; keep the Title ASCII so a stray dash/emoji
    # can never break delivery. The body (utf-8) carries the real text.
    safe_title = title.encode("ascii", "ignore").decode() or "LocalDiabetic"
    req.add_header("Title", safe_title)       # generic, no PHI
    req.add_header("Content-Type", "text/plain; charset=utf-8")
    req.add_header("User-Agent", "LocalDiabetic-Engine/0.3")  # avoid CF UA bans
    with urllib.request.urlopen(req, timeout=4) as resp:
        return 200 <= resp.status < 300


# ── Channels for a person's own reminders ────────────────────────────────────
def ch_console(reminder, on_box_text):
    print(on_box_text, flush=True)
    return True


def ch_file(reminder, on_box_text):
    local_log(on_box_text)
    return True


def ch_webhook(reminder, _on_box_text):
    """Off-box. Sends ONLY the generic nudge — never title/detail/pointer."""
    url = reminder.get("webhook_url") or os.environ.get("LD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("no webhook_url configured")
    return post_webhook(url, reminder["nudge"])


def ch_email(reminder, _on_box_text):
    """
    Off-box email copy via Resend. Sends ONLY the generic nudge (generic
    subject + body) — never title/detail/pointer. Secrets come from the
    environment so they never live in a config file:
        RESEND_API_KEY   (required)   the Resend API key
        LD_EMAIL_FROM    (optional)   e.g. 'LocalDiabetic <build@opendiabetic.com>'
        LD_EMAIL_TO      (fallback)   default recipient if reminder has no email_to
    """
    key = os.environ.get("RESEND_API_KEY")
    to = reminder.get("email_to") or os.environ.get("LD_EMAIL_TO")
    frm = os.environ.get("LD_EMAIL_FROM", "LocalDiabetic <onboarding@resend.dev>")
    if not key or not to:
        raise RuntimeError("email not configured (need RESEND_API_KEY + email_to/LD_EMAIL_TO)")
    body = json.dumps({
        "from": frm, "to": [to],
        "subject": "LocalDiabetic reminder",   # generic, no PHI
        "text": reminder["nudge"],             # generic nudge only
    }).encode("utf-8")
    req = urllib.request.Request("https://api.resend.com/emails", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "LocalDiabetic-Engine/0.3")  # CF blocks default urllib UA (err 1010)
    with urllib.request.urlopen(req, timeout=6) as resp:
        return 200 <= resp.status < 300


CHANNELS = {"console": ch_console, "file": ch_file, "webhook": ch_webhook, "email": ch_email}


def dispatch(reminder, channels, now, dry_run):
    """Fire a reminder across its channels, fail-open. Returns a result dict."""
    title = reminder.get("title", reminder["id"])
    nudge = reminder["nudge"]
    vault_ref = reminder.get("vault_ref")

    on_box_text = f"🐝 {now.strftime('%H:%M')}  {title} — {nudge}"
    if vault_ref:
        on_box_text += f"  ▸ {vault_ref}"

    left_vault = False
    delivered, failed = [], []
    for name in channels:
        fn = CHANNELS.get(name)
        if fn is None:
            failed.append({"channel": name, "error": "unknown channel"})
            continue
        if dry_run:
            delivered.append(name)
            if name in OFF_BOX_CHANNELS:
                left_vault = True
            continue
        try:
            ok = fn(reminder, on_box_text)
            delivered.append(name) if ok else failed.append({"channel": name, "error": "non-2xx/false"})
            if ok and name in OFF_BOX_CHANNELS:
                left_vault = True
        except Exception as e:  # FAIL OPEN
            failed.append({"channel": name, "error": str(e)})

    return {
        "title": title,
        "left_the_vault": left_vault,
        "off_box_payload": nudge if left_vault else None,
        "delivered": delivered,
        "failed": failed,
        "vault_ref": vault_ref,
    }


# ── Escalation to family helpers ─────────────────────────────────────────────
def escalate_to_helpers(reminder, helpers_by_id, now, dry_run):
    """
    Notify the family helper(s) named in reminder['escalate']['to'] with the
    generic escalation text. Off-box and consent-based (the user listed the
    helper and set the escalate block). Same PHI rules apply. Fails open.
    """
    esc = reminder["escalate"]
    text = esc["nudge"]
    phi = scan_phi(text)
    targets = esc.get("to", [])
    delivered, failed = [], []

    if phi:
        sys.stderr.write(
            f"[FLAG] reminder '{reminder['id']}': escalation text looks like PHI {phi} "
            f"— refusing off-box send. Keep escalation text about acknowledgment, not medicine.\n"
        )

    for hid in targets:
        helper = helpers_by_id.get(hid)
        name = helper.get("name", hid) if helper else hid
        local_log(f"⚠️  ESCALATION → {name}: {text}")  # always logged on-box
        if dry_run:
            delivered.append(hid)
            continue
        if helper is None:
            failed.append({"helper": hid, "error": "unknown helper id"})
            continue
        url = helper.get("webhook_url") or os.environ.get("LD_HELPER_WEBHOOK_URL")
        if not url:
            failed.append({"helper": hid, "error": "no webhook_url (logged on-box only)"})
            continue
        if phi:
            failed.append({"helper": hid, "error": "refused: PHI in escalation text"})
            continue
        try:
            ok = post_webhook(url, text, title="LocalDiabetic check-in")
            delivered.append(hid) if ok else failed.append({"helper": hid, "error": "non-2xx"})
        except Exception as e:  # FAIL OPEN
            failed.append({"helper": hid, "error": str(e)})

    return {"text": text, "phi": phi, "delivered": delivered, "failed": failed}


# ── Receipts ─────────────────────────────────────────────────────────────────
def _write_receipt(name_stem, receipt, now):
    os.makedirs(RECEIPTS_DIR, exist_ok=True)
    fname = f"{name_stem}-{now.strftime('%Y%m%dT%H%M%S')}.json"
    with open(os.path.join(RECEIPTS_DIR, fname), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)


def mint_fire_receipt(reminder, result, now):
    _write_receipt(f"reminder-{reminder['id']}", {
        "kind": "reminder-fired",
        "reminder_id": reminder["id"],
        "title": result["title"],
        "fired_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "channels_delivered": result["delivered"],
        "channels_failed": result["failed"],
        "left_the_vault": result["left_the_vault"],
        "off_box_payload": result["off_box_payload"],
        "phi_in_off_box_payload": scan_phi(result["off_box_payload"]),
        "vault_ref": result["vault_ref"],
        "diagnosis_given": False,
        "engine": "ld_remind/0.3",
    }, now)


def mint_ack_receipt(rid, pending, by, now, response_min):
    _write_receipt(f"ack-{rid}", {
        "kind": "reminder-acknowledged",
        "reminder_id": rid,
        "occurrence": pending["occurrence"],
        "fired_at": pending["fired_at"],
        "acknowledged_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "acknowledged_by": by,
        "response_minutes": response_min,
        "escalated_before_ack": pending.get("escalated", False),
        "diagnosis_given": False,
        "engine": "ld_remind/0.3",
    }, now)


def mint_escalation_receipt(rid, pending, esc_result, now):
    _write_receipt(f"escalation-{rid}", {
        "kind": "reminder-escalated",
        "reminder_id": rid,
        "occurrence": pending["occurrence"],
        "fired_at": pending["fired_at"],
        "deadline": pending["deadline"],
        "escalated_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "helpers_notified": esc_result["delivered"],
        "helpers_failed": esc_result["failed"],
        "left_the_vault": True,
        "off_box_payload": esc_result["text"],
        "phi_in_off_box_payload": esc_result["phi"],
        "diagnosis_given": False,
        "engine": "ld_remind/0.3",
    }, now)


# ── Tick: escalate overdue, then fire due ────────────────────────────────────
def process_escalations(reminders, helpers_by_id, state, now, dry_run):
    count = 0
    for r in reminders:
        if "escalate" not in r:
            continue
        st = state.get(r["id"], {})
        p = st.get("pending")
        if not p or p.get("escalated"):
            continue
        if now <= datetime.fromisoformat(p["deadline"]):
            continue  # still within the ack window
        esc = escalate_to_helpers(r, helpers_by_id, now, dry_run)
        prefix = "[dry-run] would escalate" if dry_run else "ESCALATED"
        print(f"{prefix}: {r['id']} → helpers={esc['delivered']} "
              f"failed={[f.get('helper') for f in esc['failed']]}", flush=True)
        if not dry_run:
            mint_escalation_receipt(r["id"], p, esc, now)
            p["escalated"] = True
            st["pending"] = p
            state[r["id"]] = st
        count += 1
    return count


def fire_due(reminders, state, now, dry_run):
    fired = 0
    for r in reminders:
        rid = r["id"]
        r["_last_fire_date"] = state.get(rid, {}).get("last_fire_date")

        channels = list(r.get("channels", ["console", "file"]))
        if set(channels) & OFF_BOX_CHANNELS:
            leak = scan_phi(r["nudge"])
            if leak:
                sys.stderr.write(
                    f"[FLAG] reminder '{rid}': off-box nudge looks like PHI {leak} "
                    f"— refusing off-box delivery. Make the nudge generic.\n"
                )
                channels = [c for c in channels if c not in OFF_BOX_CHANNELS]

        is_due, occ = occurrence_for(r, now)
        if not is_due:
            continue
        if state.get(rid, {}).get("last_occurrence") == occ:
            continue  # already fired this occurrence

        result = dispatch(r, channels, now, dry_run)
        prefix = "[dry-run] would fire" if dry_run else "fired"
        leftmark = " → off-box" if result["left_the_vault"] else " (local only)"
        esc_note = "  [escalates if no ack]" if "escalate" in r else ""
        print(f"{prefix}: {rid}{leftmark}  delivered={result['delivered']} "
              f"failed={[f.get('channel') for f in result['failed']]}{esc_note}", flush=True)

        if not dry_run:
            mint_fire_receipt(r, result, now)
            entry = state.get(rid, {})
            entry["last_occurrence"] = occ
            entry["last_fire_date"] = now.strftime("%Y-%m-%d")
            if "escalate" in r:
                after = r["escalate"].get("after_minutes", 30)
                deadline = now + timedelta(minutes=after)
                entry["pending"] = {
                    "occurrence": occ,
                    "fired_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
                    "deadline": deadline.strftime("%Y-%m-%dT%H:%M:%S"),
                    "escalated": False,
                }
            state[rid] = entry
        fired += 1
    return fired


def tick(reminders, helpers, now, dry_run):
    state = load_state()
    helpers_by_id = {h["id"]: h for h in helpers}
    esc = process_escalations(reminders, helpers_by_id, state, now, dry_run)
    fired = fire_due(reminders, state, now, dry_run)
    if not dry_run:
        save_state(state)
    if fired == 0 and esc == 0:
        print("nothing due", flush=True)


# ── Acknowledge ──────────────────────────────────────────────────────────────
def acknowledge(rid, by, now):
    state = load_state()
    st = state.get(rid, {})
    p = st.get("pending")
    if not p:
        print(f"no pending reminder to acknowledge for '{rid}'", flush=True)
        return
    fired = datetime.strptime(p["fired_at"], "%Y-%m-%dT%H:%M:%S")
    response_min = round((now - fired).total_seconds() / 60, 1)
    mint_ack_receipt(rid, p, by, now, response_min)
    local_log(f"✓ ACK {rid} by {by} ({response_min} min)")
    st.pop("pending", None)
    st["last_ack_occurrence"] = p["occurrence"]
    state[rid] = st
    save_state(state)
    extra = " (was already escalated)" if p.get("escalated") else ""
    print(f"✓ acknowledged '{rid}' by {by} — {response_min} min after it fired{extra}", flush=True)


def show_pending(now):
    state = load_state()
    any_p = False
    for rid, st in state.items():
        p = st.get("pending")
        if not p:
            continue
        any_p = True
        if p.get("escalated"):
            print(f"  {rid}: ⚠️  ESCALATED (fired {p['fired_at']}, deadline {p['deadline']})")
        else:
            overdue = now > datetime.strptime(p["deadline"], "%Y-%m-%dT%H:%M:%S")
            mark = "OVERDUE — will escalate next tick" if overdue else "awaiting ack"
            print(f"  {rid}: {mark} (escalates at {p['deadline']})")
    if not any_p:
        print("  nothing pending acknowledgment")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="LocalDiabetic Reminder Engine (the Nudge)")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--dry-run", action="store_true", help="show what would happen; change nothing")
    ap.add_argument("--at", help="simulate a time, ISO e.g. 2026-06-20T08:00")
    ap.add_argument("--list", action="store_true", help="list configured reminders and exit")
    ap.add_argument("--ack", metavar="ID", help="acknowledge a pending reminder")
    ap.add_argument("--by", default="user", help="who is acknowledging (for the receipt)")
    ap.add_argument("--pending", action="store_true", help="show reminders awaiting ack / escalated")
    args = ap.parse_args()

    now = datetime.strptime(args.at, "%Y-%m-%dT%H:%M") if args.at else datetime.now()

    if args.pending:
        show_pending(now)
        return
    if args.ack:
        acknowledge(args.ack, args.by, now)
        return

    reminders, helpers = load_config(args.config)

    if args.list:
        for r in reminders:
            ch = ",".join(r.get("channels", []))
            esc = "  ⤴ escalates" if "escalate" in r else ""
            print(f"  {r['id']:<18} {r['schedule']:<28} [{ch}]  {r.get('title','')}{esc}")
        if helpers:
            print("  helpers: " + ", ".join(h.get("id") for h in helpers))
        return

    tick(reminders, helpers, now, args.dry_run)


if __name__ == "__main__":
    main()
