# Home Assistant → LocalDiabetic bridge

The whole spine: cheap local Zigbee sensors → **Home Assistant on the box** → one webhook into the
LocalDiabetic dashboard's **`/api/event`** → it logs a **Life event** (visible on the dashboard) and, for
alerts, fires a **generic** nudge to the phone. PHI never leaves the box; only a generic alert crosses.

```
Zigbee sensors → ZBDongle-E → Home Assistant (NAS/edge)
   → rest_command POST → http://<box>:8081/api/event → Life tab + (alert) → ntfy nudge
```

## 1. Point HA at the box

Add to Home Assistant `configuration.yaml` (replace host/port + token):

```yaml
rest_command:
  localdiabetic_event:
    url: "http://127.0.0.1:8081/api/event"     # the LocalDiabetic dashboard on the same box
    method: POST
    headers:
      Content-Type: application/json
      X-LD-Token: !secret localdiabetic_token   # optional; matches LD_EVENT_TOKEN if set
    payload: >
      {"type":"{{ type }}","title":"{{ title }}","message":"{{ message }}",
       "severity":"{{ severity }}","notify":{{ notify | default(false) | tojson }},
       "nudge":"{{ nudge | default(title) }}","source":"home-assistant"}
```

Event fields: `type` (fridge/help/meds/foot/glucose/safety/device/supply), `title`, `message`,
`severity` (info/good/warn/alert), `notify` (true → also push a **generic** nudge to the phone),
`nudge` (the generic phone text — keep it free of any health detail).

## 2. The starter-kit automations

**Insulin fridge out of range (the marquee):**
```yaml
automation:
  - alias: "Insulin fridge temperature alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.insulin_fridge_temp
        above: 8          # °C — insulin spoils warm
        for: "00:10:00"
      - platform: numeric_state
        entity_id: sensor.insulin_fridge_temp
        below: 2          # °C — or a freeze
        for: "00:10:00"
    action:
      - service: rest_command.localdiabetic_event
        data:
          type: fridge
          title: "Check the fridge"
          message: "The fridge temperature is out of the safe range."
          severity: alert
          notify: true
          nudge: "🧊 Please check your fridge — temperature is out of range."
```

**One-press help button (Aqara mini switch):**
```yaml
  - alias: "Help button pressed"
    trigger: { platform: state, entity_id: sensor.help_button_action, to: "hold" }
    action:
      - service: rest_command.localdiabetic_event
        data: { type: help, title: "Help requested", message: "The help button was pressed.",
                severity: alert, notify: true, nudge: "🆘 Help button pressed at home." }

  - alias: "Took my meds button"
    trigger: { platform: state, entity_id: sensor.help_button_action, to: "single" }
    action:
      - service: rest_command.localdiabetic_event
        data: { type: meds, title: "Took my meds ✓", severity: good }
```

**Med cabinet not opened by noon (door sensor):**
```yaml
  - alias: "Med cabinet not opened"
    trigger: { platform: time, at: "12:00:00" }
    condition:
      - condition: state
        entity_id: binary_sensor.med_cabinet
        state: "off"          # never opened today
    action:
      - service: rest_command.localdiabetic_event
        data: { type: meds, title: "Medication reminder",
                message: "The medication cabinet hasn't been opened yet today.",
                severity: warn, notify: true, nudge: "💊 Don't forget your medications today." }
```

## 3. Firewall notes (non-negotiable)
- HA runs **on the box** (Synology Container Manager or native on the Jetson/Mac-mini). Sensor data and
  the detail stay in HA on the box.
- `/api/event` logs the full event **locally**; only a **generic** `nudge` ever goes off-box, and the
  dashboard re-scans it for PHI before pushing (`notify_generic`).
- Keep `nudge` text generic — no readings, no doses. The detail lives on the box; the phone gets the gist.
- Set `LD_EVENT_TOKEN` in the dashboard env + `localdiabetic_token` in HA secrets to keep stray LAN devices
  from posting events.
