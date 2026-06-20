#!/usr/bin/env python3
"""
LocalDiabetic Reminder Engine — "the Nudge"
===========================================

The second half of the box: Vault + Nudge.

This engine sits ON TOP of the Home Vault folders and fires gentle, on-time
reminders — foot check, medications, supply reorders, appointments — to the
local box and (optionally) to a phone/watch over a bridge you own.

THE INVARIANT, ENFORCED STRUCTURALLY
------------------------------------
This engine NEVER reads the contents of a record. It only ever emits the
generic `nudge` string the user declared in reminders.json. The medical
detail (which med, which dose, which wound) stays in the vault as a pointer
(`vault_ref`) the user follows ON THE BOX. PHI cannot leak because the engine
never loads PHI in the first place.

Off-box channels (a webhook to your phone) carry ONLY the declared generic
nudge. Local channels (console, on-box log) may show the title and pointer.

Every fired reminder mints a receipt into ../14-receipts/ proving what fired,
whether anything left the vault, and that no diagnosis was given.

FAIL OPEN
---------
Every channel is wrapped so a failure NEVER blocks the others. The local log
is the always-works rail and takes precedence — a dead phone bridge can never
stop the foot-check reminder from landing on the box. (Locked doctrine:
optional components in a delivery path fail open.)

USAGE
-----
    python3 ld_remind.py                 # one tick: fire everything due now
    python3 ld_remind.py --dry-run       # show what WOULD fire, change nothing
    python3 ld_remind.py --at 2026-06-20T08:00   # simulate a time (testing)
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

# Off-box channels carry only the declared generic nudge — never title/detail.
OFF_BOX_CHANNELS = {"webhook"}

# A backstop scan. The real protection is that the engine never loads PHI;
# this just flags an author who accidentally put detail in a generic nudge.
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
    return cfg.get("reminders", [])


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


# ── Schedule parsing & due logic ─────────────────────────────────────────────
def parse_hhmm(s):
    h, m = s.split(":")
    return int(h), int(m)


def occurrence_for(reminder, now):
    """
    Return (is_due, occurrence_key) for a reminder at time `now`.

    occurrence_key uniquely identifies the specific scheduled firing so we
    fire each occurrence exactly once. State stores the last fired key.

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
        today = WEEKDAYS[now.weekday()]
        if today not in days:
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
        key = now.strftime("%Y-%m-%d")
        return (True, key)

    if kind == "once":
        due = datetime.strptime(parts[1] + " " + parts[2], "%Y-%m-%d %H:%M")
        key = due.strftime("%Y-%m-%dT%H:%M")
        # one-shot: fire from due time up to grace; key never repeats
        return (due <= now <= due + grace, key)

    sys.stderr.write(f"[warn] reminder {reminder.get('id')}: unknown schedule '{sched}'\n")
    return (False, None)


# ── PHI guard ────────────────────────────────────────────────────────────────
def scan_phi(text):
    low = text.lower()
    return [h.strip() for h in PHI_HINTS if h in low]


def off_box_payload(reminder):
    """The ONLY thing allowed to leave the box: the declared generic nudge."""
    return reminder["nudge"]


# ── Channels (each fails open) ───────────────────────────────────────────────
def ch_console(reminder, on_box_text):
    print(on_box_text, flush=True)
    return True


def ch_file(reminder, on_box_text):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOCAL_LOG, "a", encoding="utf-8") as f:
        f.write(on_box_text + "\n")
    return True


def ch_webhook(reminder, _on_box_text):
    """Off-box. Sends ONLY the generic nudge. Times out fast, never raises up."""
    url = reminder.get("webhook_url") or os.environ.get("LD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("no webhook_url configured")
    payload = off_box_payload(reminder)
    data = payload.encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Title", "LocalDiabetic")  # generic, no PHI
    req.add_header("Content-Type", "text/plain; charset=utf-8")
    with urllib.request.urlopen(req, timeout=4) as resp:
        return 200 <= resp.status < 300


CHANNELS = {"console": ch_console, "file": ch_file, "webhook": ch_webhook}


def dispatch(reminder, channels, now, dry_run):
    """
    Fire a reminder across its channels, fail-open. Returns a result dict
    describing exactly what happened (used for the receipt).
    """
    title = reminder.get("title", reminder["id"])
    nudge = reminder["nudge"]
    vault_ref = reminder.get("vault_ref")
    phi_sensitive = reminder.get("phi_sensitive", False)

    # On-box text may include the title + pointer (detail stays local).
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
            (delivered if ok else failed).append(
                name if ok else {"channel": name, "error": "non-2xx/false"}
            )
            if ok and name in OFF_BOX_CHANNELS:
                left_vault = True
        except Exception as e:  # FAIL OPEN — never let one channel kill the rest
            failed.append({"channel": name, "error": str(e)})

    return {
        "title": title,
        "phi_sensitive": phi_sensitive,
        "left_the_vault": left_vault,
        "off_box_payload": nudge if left_vault else None,
        "delivered": delivered,
        "failed": failed,
        "vault_ref": vault_ref,
    }


# ── Receipts ─────────────────────────────────────────────────────────────────
def mint_receipt(reminder, result, now):
    os.makedirs(RECEIPTS_DIR, exist_ok=True)
    phi_flags = scan_phi(result["off_box_payload"]) if result["off_box_payload"] else []
    receipt = {
        "kind": "reminder-fired",
        "reminder_id": reminder["id"],
        "title": result["title"],
        "fired_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "channels_delivered": result["delivered"],
        "channels_failed": result["failed"],
        "left_the_vault": result["left_the_vault"],
        "off_box_payload": result["off_box_payload"],
        "phi_in_off_box_payload": phi_flags,          # MUST be [] — backstop
        "vault_ref": result["vault_ref"],             # pointer, stayed local
        "diagnosis_given": False,
        "engine": "ld_remind/0.1",
    }
    fname = f"reminder-{reminder['id']}-{now.strftime('%Y%m%dT%H%M%S')}.json"
    with open(os.path.join(RECEIPTS_DIR, fname), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
    return receipt, phi_flags


# ── Main tick ────────────────────────────────────────────────────────────────
def tick(reminders, now, dry_run):
    state = load_state()
    fired = 0
    for r in reminders:
        rid = r["id"]
        # thread interval state in for the due check
        r["_last_fire_date"] = state.get(rid, {}).get("last_fire_date")

        # Backstop: refuse to even configure a nudge that carries PHI off-box.
        if set(r.get("channels", [])) & OFF_BOX_CHANNELS:
            leak = scan_phi(r["nudge"])
            if leak:
                sys.stderr.write(
                    f"[FLAG] reminder '{rid}': off-box nudge looks like PHI {leak} "
                    f"— refusing off-box delivery. Make the nudge generic.\n"
                )
                r = dict(r, channels=[c for c in r["channels"] if c not in OFF_BOX_CHANNELS])

        is_due, occ = occurrence_for(r, now)
        if not is_due:
            continue
        if state.get(rid, {}).get("last_occurrence") == occ:
            continue  # already fired this occurrence

        result = dispatch(r, r.get("channels", ["console", "file"]), now, dry_run)
        prefix = "[dry-run] would fire" if dry_run else "fired"
        leftmark = " → off-box" if result["left_the_vault"] else " (local only)"
        print(f"{prefix}: {rid}{leftmark}  delivered={result['delivered']} "
              f"failed={[f.get('channel') for f in result['failed']]}", flush=True)

        if not dry_run:
            _, phi_flags = mint_receipt(r, result, now)
            if phi_flags:
                sys.stderr.write(f"[FLAG] {rid}: PHI in off-box payload {phi_flags}\n")
            state[rid] = {
                "last_occurrence": occ,
                "last_fire_date": now.strftime("%Y-%m-%d"),
            }
        fired += 1

    if not dry_run:
        save_state(state)
    if fired == 0:
        print("nothing due", flush=True)
    return fired


def main():
    ap = argparse.ArgumentParser(description="LocalDiabetic Reminder Engine (the Nudge)")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--dry-run", action="store_true", help="show what would fire; change nothing")
    ap.add_argument("--at", help="simulate a time, ISO e.g. 2026-06-20T08:00")
    ap.add_argument("--list", action="store_true", help="list configured reminders and exit")
    args = ap.parse_args()

    reminders = load_config(args.config)

    if args.list:
        for r in reminders:
            ch = ",".join(r.get("channels", []))
            print(f"  {r['id']:<18} {r['schedule']:<28} [{ch}]  {r.get('title','')}")
        return

    now = datetime.strptime(args.at, "%Y-%m-%dT%H:%M") if args.at else datetime.now()
    tick(reminders, now, args.dry_run)


if __name__ == "__main__":
    main()
