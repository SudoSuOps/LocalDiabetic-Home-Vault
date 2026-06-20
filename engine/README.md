# The Nudge — LocalDiabetic Reminder Engine

**Phase 2 of the box.** The Vault holds the papers; the Nudge keeps you on time —
foot checks, medications, supply reorders, appointments. Gentle, local, on schedule.

> Optional. The Vault works fine on its own. Add the Nudge when you want reminders.

---

## The promise (and how it's kept)

**The engine never reads a record.** It only ever sends the generic reminder text
*you* wrote (the `nudge` field). The medical detail — which med, which dose, which
wound — stays in the vault as a pointer you follow **on your own box**.

That means a reminder going to your phone says *"Morning routine reminder ⏰"* — never
*"take 10 units of insulin."* PHI can't leak to your phone because the engine never
loads PHI in the first place. (See `../HARD-INVARIANT.md`.)

Every reminder that fires leaves a **receipt** in `../14-receipts/` proving what fired,
whether anything left the box, and that no diagnosis was given.

And every delivery channel **fails open**: if your phone bridge is down, the local log
still gets the reminder. A dead bridge can never silence your foot-check.

---

## Setup (2 minutes)

```bash
cd engine
cp reminders.example.json reminders.json   # your schedule — stays on your box (gitignored)
nano reminders.json                         # edit times and reminders

python3 ld_remind.py --list                 # see your reminders
python3 ld_remind.py --dry-run --at 2026-06-20T08:00   # test without firing
python3 ld_remind.py                         # one real tick: fire what's due now
```

No `pip install`. Python 3.8+ standard library only.

---

## Reminder format

Each reminder in `reminders.json`:

| Field | Meaning |
|---|---|
| `id` | Unique short name (used in receipts and state). |
| `title` | Shown **on the box** only. |
| `nudge` | The **only** text allowed to leave the box. Keep it generic — no meds, doses, or numbers. |
| `schedule` | When it fires (see below). |
| `vault_ref` | Pointer to the vault file with the detail. Stays local. |
| `channels` | Where it goes: `console`, `file` (on-box log), `webhook` (off-box phone/watch). |
| `phi_sensitive` | `true` = extra care; the title/detail never leave the box. |
| `grace_hours` | If the box was off at the scheduled time, still fire up to N hours late (default 12). |
| `webhook_url` | Per-reminder webhook (or set `LD_WEBHOOK_URL` env for all). |

### Schedules

```
daily@08:00                 every day at 08:00
weekly@SUN@18:00            every Sunday at 18:00  (MON TUE WED THU FRI SAT SUN)
weekly@MON,THU@09:00        Mondays and Thursdays at 09:00
interval_days@2@09:00       every 2 days at 09:00 (e.g. dressing changes)
once@2026-06-26@18:00       a single one-shot reminder (an appointment, a refill-by)
```

---

## Running it on a schedule

The engine does **one tick per run** — it fires whatever is due, then exits. Run it
every minute with whatever scheduler your box already has.

**cron (Linux / NAS):**
```cron
* * * * * /usr/bin/python3 /path/to/localdiabetic/engine/ld_remind.py >> /path/to/localdiabetic/engine/.state/cron.log 2>&1
```

**systemd timer (Linux):** a `ld-remind.service` (Type=oneshot running the script) +
`ld-remind.timer` with `OnCalendar=*:0/1`.

**Synology DSM:** Control Panel → Task Scheduler → Create → Scheduled Task →
User-defined script, set to run every minute, command:
`python3 /volume1/localdiabetic/engine/ld_remind.py`

---

## The phone/watch bridge — keep it sovereign

The `webhook` channel POSTs the generic nudge to a URL. The sovereign choice is to run
your **own** push server on the NAS so nudges never touch a third party:

- **[ntfy](https://ntfy.sh)** self-hosted on the NAS → the ntfy app on your iPhone/Apple
  Watch subscribes over your home network or VPN. Free, no account, your data, your box.

Point `webhook_url` (or `LD_WEBHOOK_URL`) at your ntfy topic. The engine sends only the
generic nudge text with a generic `LocalDiabetic` title — never PHI.

Don't want anything leaving the box at all? Drop `webhook` from `channels`. The console
and on-box log still work. **Local-only is a fully supported mode.**

---

## What it writes

| Path | What |
|---|---|
| `engine/.state/last_fired.json` | Which occurrences already fired (so nothing double-fires). Gitignored. |
| `engine/.state/notifications.log` | On-box log of every nudge. Gitignored. |
| `../14-receipts/reminder-*.json` | A receipt per fired reminder. Gitignored (your activity stays local). |

---

## Known limits (v0.1, honest)

- Tick-based: a reminder fires on the first run **after** its scheduled time, within
  `grace_hours`. If your scheduler runs every 5 minutes, a nudge can be up to 5 min late.
- No snooze / acknowledge yet — a reminder fires once per occurrence. Ack + escalation
  ("nudge a family helper if not acknowledged") is a Phase 2.1 candidate.
- `webhook` delivery is best-effort and fails open; it does not retry.

---

*Vault + Nudge. Powered by OpenDiabetic. Your data stays yours.*
