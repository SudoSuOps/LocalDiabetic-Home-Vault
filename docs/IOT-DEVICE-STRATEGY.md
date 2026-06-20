# LocalDiabetic — IoT & Edge Device Strategy
*Research by a 9-hack swarm · light-lift, real-world utility, firewall-safe · 2026-06-20*

This is a synthesis task — the research is all provided, no tools needed. Here is the decision-ready report.

---

# LocalDiabetic Device Strategy — Decision-Ready Report for DonnyMack

**The whole game in one line:** buy *dumb, cheap, local-first hardware*, put a single Zigbee/Thread radio on the box we already ship, let Home Assistant on the NAS/edge do the sensing, and let the Nudge engine do the only thing that ever leaves the house — a generic, non-PHI ping. Every "smart" device that phones a vendor cloud is a firewall violation and gets declined, no matter how slick. We stay in doctrine: **monitor + remind, never diagnose, never dose.**

---

## 1. THE STARTER KIT — Ship It This Quarter

Five devices. One radio + four sensors that turn the box into a real diabetic-safety net. Total hardware **~$95–115/home**, all light-lift (peel-and-stick / plug-in), all 100% local. This is the pilot.

| # | Device | ~Cost | Why it matters (diabetic-life utility) | How it plugs into the box |
|---|---|---|---|---|
| **0** | **Sonoff ZBDongle-E** (Zigbee USB coordinator) — *the enabler, buy once per home* | **$17–20** | Nothing else works local without it. This single stick is what keeps the entire kit behind the firewall — no Aqara hub, no vendor account, no internet. | Plug into NAS or edge box USB → HA ZHA/Zigbee2MQTT auto-detects. Every sensor below joins its mesh on-box. |
| **1** | **Zigbee temp sensor w/ external waterproof probe** (insulin fridge monitor) | **$15–20** | **The marquee device.** Insulin is ruined silently by heat (>30°C) or a freeze — a power blip can destroy a month's supply overnight. Probe sits *inside* the fridge where the insulin actually is. | Probe inside, body outside → Zigbee → HA threshold breach → Nudge fires "check the fridge." |
| **2** | **Aqara Wireless Mini Switch** (one-press help / "I took my meds") | **$15–20** | One big tactile button, no screen, three programmable actions: press = "took meds" (logged on-box), long-press = "I need help" → family safety net. Perfect for a 75-yr-old. | Paired to the ZBDongle-E (**never** the Aqara hub) → HA → Nudge / family escalation. |
| **3** | **Sonoff SNZB-04P** (door/cabinet contact sensor) | **$13.50** | Med-cabinet "did they open it today?" → if not opened by noon, Nudge fires. Doubles as front-door safety (left and didn't return). 5-yr battery. | Peel-and-stick magnet pair → Zigbee → HA living-alone checks → Nudge. |
| **4** | **Big-display dementia day-clock** (American Lifetime / ORKA / KASTISS) | **$40–70** | Highest utility-per-dollar accessibility device, period. Spells out full day/date/time, readable from 20ft, 3+ med alarms, battery backup. The thing a volunteer has working in 5 minutes. | Standalone (no network = zero firewall risk). Complements the box; it's the visible, comforting anchor on the counter. |

**Why this five and not others:** it covers the four pillars of daily diabetic safety — *insulin integrity, med adherence, one-press help, and accessible time/reminders* — at the lowest possible cost and install effort, with zero PHI ever leaving the home. The day-clock is deliberately offline-by-construction so even a member who never finishes the HA setup still gets real value on day one.

---

## 2. THE FULL MENU — Tiered by Need

| Need | **Starter** (cheap, light-lift, ship-first) | **Better** (more capability, one-time volunteer setup) | **Premium** (only when justified) |
|---|---|---|---|
| **Connectivity spine** | Sonoff ZBDongle-E ($17–20) on existing NAS/edge | HA Connect ZBT-2 ($49, adds Thread/Matter) | HA Green $159 + dongle (*only if no NAS/edge to host HA*) |
| **Insulin fridge** | Zigbee probe temp sensor ($15–20) | + ThirdReality power-metering plug on fridge ($15, redundant "fridge died" alarm) | — |
| **Glucose / CGM** | Contour Next One BT fingerstick ($20–35, plug-and-play, big display) | Dexcom G7 → xDrip+ → self-hosted Nightscout on NAS ($0 bridge, reuse phone) | Libre 3/3+ → Juggluco offline → local Nightscout (dev-grade, assign volunteer) |
| **Med adherence** | LiveFine 28-Day auto dispenser, **non-WiFi LCD SKU** ($60–90, no subscription) | + $10 Zigbee vibration/contact sensor on the lid (on-box "was it taken?" signal) | DIY HA reminder loop (light + button dismiss, ~$25–60 parts) — the native moat |
| **Blood pressure** | Greater Goods big-backlit cuff ($40–60, member keys reading in) | Omron 10-Series BP7450 via `hass-omron` local BLE ($58–105, no Omron cloud) | — |
| **Pulse oximeter** | $15–25 dumb fingertip clip (air-gapped, best real-world choice) | CONTEC PC-60FW via ESPHome local read ($45–60) | — |
| **Weight / fluid trend** | $15 analog scale + manual Nudge log | Xiaomi Body Comp Scale 2 + ESP32 BLE proxy ($48 + $15, no Mi/Zepp account) | — |
| **Foot temp (highest-stakes)** | Generic non-contact IR thermometer ($20–40) + Nudge foot-check routine | TempTouch contact IR ($150, Rx, still fully local — just displays a number) | — |
| **Fall detection** | — | Seeed MR60FDA2 mmWave ($25, pre-flashed ESPHome, radar = no camera) | Aqara FP2 *(local-API path only; flagged for diagnosis-drift — see Avoid)* |
| **Living-alone safety** | Sonoff SNZB-04P door ($13.50), Aqara motion P1 ($20) | Zigbee under-mattress bed-occupancy mat ($25–40) | — |
| **Leak / flood** | ThirdReality Zigbee leak 4-pack ($50, ~$12.50 ea, 120dB) | — | — |
| **Voice / hands-free** | Big-display day-clock ($40–70, offline) | HA Voice Preview Edition ($59, fully local Whisper/Piper on edge box) | ESP32-S3-BOX-3 Wyoming satellite ($15–55, DIY) |

---

## 3. THE CONNECTIVITY SPINE — The Simplest Local-First Glue

**One radio + Home Assistant + one webhook. That's the whole spine.**

```
[Zigbee sensors: fridge probe, button, door, bed mat, leak]
        │  (Zigbee mesh — mains plugs self-heal/repeat)
        ▼
[Sonoff ZBDongle-E]  →  [Home Assistant on NAS/edge]
   USB coordinator       (Synology Container Manager docker, ~200-400MB RAM,
                          OR native on Jetson/Mac-mini)
        │
   local automation fires one-line rest_command POST (local_only: true → 127.0.0.1)
        ▼
[Nudge engine  ld_remind.py]  →  generic non-PHI nudge → ntfy → phone/watch
```

**Why it holds the firewall by design:**
- **HA runs ON the box we already ship.** No new brain hardware — only the ~$20 USB stick. Fully supported on Synology DSM7+ Container Manager and natively on the Jetson/Mac-mini.
- **The integration seam is literally one line:** an HA automation triggers a `rest_command` POST to `127.0.0.1` on the existing `ld_remind.py`. HA does the *sensing*; the Nudge does the *generic off-box alert*. PHI (which sensor, what reading) stays in HA on the box; only a `vault_ref`-style generic nudge crosses the boundary — unchanged from the P2 design already live on the NAS.
- **Default ship = ZBDongle-E ($17–20).** Upgrade to **HA Connect ZBT-2 ($49)** only when a member's kit needs Thread/Matter; it does Zigbee *or* Thread at a time, so ship both dongles (~$67) rather than fighting MultiPAN.
- **Hard rule for the spine:** Home Assistant on-box is the **source of truth**. We may let a Matter device *also* appear in Apple/Google Home for member convenience, but the safety automation NEVER routes through a cloud assistant.

**Volunteer reality:** all of this is "plug the USB stick in, HA discovers it." The member logs into nothing and only ever sees the big-button ntfy nudge on their phone.

---

## 4. AVOID LIST — Decline These (and Why)

| Device | Category | Why declined |
|---|---|---|
| **Dexcom Share / LibreLinkUp / CareLink** | CGM cloud paths | **Firewall violation** — every reading lands on a vendor server. The HA "Dexcom" integration is *cloud polling*, not a local read. Use xDrip+/Juggluco→local Nightscout instead. |
| **Medtronic Guardian → CareLink** | CGM | Closed cloud, no community local stack worth shipping. |
| **Hero Health** | Pill dispenser | $99 + **$30/mo forever, bricks if subscription lapses** — both a firewall violation and a member-harm risk (a free program can't depend on a device that dies on a missed bill). |
| **MedMinder** | Pill dispenser | $125/mo cellular-monitored by design; its whole value is the cloud monitoring we already do locally. |
| **e-pill MedSmart PLUS / Voice-Pro · AdhereTech** | Pill / smart cap | The PLUS/cellular tiers ship dose-event PHI to a vendor cloud. Buy the stand-alone e-pill only; decline the monitored tiers. |
| **Podimetrics SmartMat / SmartMat+** | Foot-temp mat | Cellular mat → Podimetrics cloud + **nurse review**. Firewall violation by design, no consumer price. |
| **Siren Socks** | Foot-temp sock | Sensors → Siren cloud → licensed-nurse monitoring, $240/yr. Firewall violation. |
| **Withings BPM Connect / Body scales** | BP / scale | Great hardware, but HA integration is cloud-OAuth-polled with a public webhook — data provably transits Withings servers. |
| **GrandPad** | Senior tablet | Cloud-locked, carrier-locked, $25/mo (~$275/yr) — breaks the free-to-member, no-strings model. |
| **Amazon Echo Show / Google Nest Hub** | Voice/display | No local-only mode; every voice request and reminder forced through a vendor cloud. |
| **Apple HomePod mini as the brain** | Hub | Requires Apple ID/iCloud; automation logic lives in Apple's cloud. Fine as a convenience endpoint, never as the LocalDiabetic brain. |
| **Aqara / Tuya / SmartThings *hubs* + all Wi-Fi "smart" SKUs** | Connectivity | Same physical sensor, opposite privacy outcome — the brand hub forces a vendor account/cloud. Always buy the bare **Zigbee SKU** + our coordinator. |
| **Aqara Presence Sensor FP2** | Fall detection | Wi-Fi to Aqara cloud **and** its "fall detection" marketing drifts toward diagnosis. Use Seeed MR60FDA2 (radar, local) instead. If ever used, local-API only and framed as "movement," never medical. |
| **Any vendor companion app** (Omron Connect, Mi Fit/Zepp, Health Mate) | All | The app *is* the cloud leak. The local-first benefit only holds if the volunteer **never installs the vendor app** and pairs the device directly to the box. Bake into the setup checklist. |

---

## 5. TOP 3 BIG-IMPACT PLAYS — What Most Changes a Diabetic's Daily Safety

These are the moves where the device most directly prevents the bad day. Donovan has lived every one of these — they're chosen from his own scars.

### Play 1 — Insulin-Fridge Monitoring (the silent-spoilage killer)
**Zigbee probe temp sensor (~$15–20) inside the fridge + optional power-metering plug ($15).**
Insulin is destroyed silently by heat or a freeze, and a power blip overnight can ruin a month's supply with zero warning. The probe reads the *actual interior temp*; HA fires the Nudge on a threshold breach or when fridge wattage drops to zero. **Highest real-utility-per-dollar device in the entire catalog**, fully local, light-lift. This is the cheapest catastrophe we prevent.

### Play 2 — Foot-Temp Early-Warning (the amputation preventer, done firewall-clean)
**Generic non-contact IR thermometer (~$20–40) + a Nudge foot-check routine.**
This is the highest *clinical* stakes device and the one closest to Donovan's own continuum. We **cannot** ship Podimetrics or Siren — they're nurse-monitored cloud services that break the firewall by design (and cost $240/yr). Instead we own the doctrine-clean version: member measures 6 plantar points/foot daily, reading logged to the vault, and the **Nudge applies the published rule as a reminder, not a verdict** — "the same spot has been 2°C+ warmer than the other foot for 2 days; time to call Dr. G." Clinically this is the *same signal* the expensive mats use (early detection prevents up to ~75% of ulcers) at ~1% of the cost, with **zero data leaving the house.** Strictly: the box says "call your clinician," never "you have an ulcer."

### Play 3 — One-Press Help + Med-Adherence Loop (the dignity + safety net)
**Aqara Mini Switch (~$15–20) + LiveFine non-WiFi dispenser ($60–90) + a $10 Zigbee lid sensor.**
The button gives a 75-yr-old a single big tactile press: "I took my meds" (logged on-box) or long-press "I need help" → family safety net — no screen, no app. Paired with the offline LiveFine dispenser (loud local alarm, locking lid) and a cheap Zigbee sensor on its lid, the box *knows* whether the dose was taken and runs missed-dose family escalation **100% locally**. This is the only adherence path where the dose event never leaves the box — the exact feature Hero/MedMinder sell for $30–125/mo via a firewall-violating cloud, delivered here for one-time hardware and no subscription.

---

### Honest caveats to carry into the pilot
- **CGM is the one genuinely hard category.** Modern CGMs are cloud-locked by design; the only firewall-clean paths (xDrip+/Juggluco → self-hosted Nightscout) are developer-grade and need the paid volunteer. For an elderly member not ready for a sideloaded rig, the **Contour Next One fingerstick ($20–35)** is the honest, plug-and-play starting point.
- **The ESP32-BLE devices** (Omron cuff, Xiaomi scale, CONTEC oximeter) deliver real local data but add one-time volunteer flashing. Where light-lift beats data capture, the **air-gapped dumb version** (plain cuff/scale/oximeter + manual Nudge log) is the doctrine-safe minimum and often the better real-world choice.
- **Diagnosis drift is the standing risk across every category.** Code every threshold as a *reminder rule that says "call your clinician,"* never a verdict. AFib flags, temp asymmetry, BP zones = raw device output that we log and nudge around, never a LocalDiabetic interpretation.
- **The subscription test is also a member-harm test.** We decline anything that bricks on a lapsed bill — a free, no-strings program cannot ship a device that dies when a payment fails.


---

# Appendix — Category Research


## Glucose Monitoring

I have everything needed. Here is the research section.

---

# Glucose & CGM Connectivity for LocalDiabetic

The hard truth up front: **most modern CGMs are cloud-locked by design.** The sensor talks Bluetooth to the *vendor's own phone app*, which encrypts the raw data and ships it to the vendor cloud (Dexcom Share / Abbott LibreView). The "official" Home Assistant Dexcom integration is **Cloud Polling** — it logs into Dexcom's servers, not your sensor. So the firewall-clean path is **not** the official integrations; it's the open-source community stack (xDrip+ / Juggluco / self-hosted Nightscout) that can pull readings on the member's own box. There are real local routes, but they take a volunteer to set up, and a few are flat-out firewall violations to be flagged.

## How the data actually flows (the 4 routes)

1. **Vendor cloud (FIREWALL VIOLATION)** — Dexcom Share, LibreLinkUp, Medtronic CareLink. Readings sit on a corporate server. The HA "Dexcom" and HA "Nightscout-via-LibreLinkUp" paths use this. **Flag, do not recommend** unless nothing else is possible.
2. **Phone-as-local-bridge (BEST for CGM)** — an Android phone running **xDrip+** or **Juggluco** captures the sensor over Bluetooth/NFC *on-device* and pushes to a **self-hosted Nightscout** on the LocalDiabetic NAS over the home LAN. No vendor cloud touched. This is the firewall-clean CGM path.
3. **Self-hosted Nightscout on the box** — the local datastore + REST API the NAS/edge runs. Home Assistant's **Nightscout** integration is **local polling** against *your* instance — clean.
4. **Fingerstick Bluetooth meter** — older, simpler. A few meters (Contour Next One) can be read by the open stack without an account.

## Comparison table

| Device / path | Diabetic utility | Install effort | Approx cost | Privacy / firewall fit | LocalDiabetic integration |
|---|---|---|---|---|---|
| **Dexcom G7 → xDrip+ (native local BT)** | High — real-time CGM, alarms | Medium (sideload xDrip+ ≥2026.05.06 on a spare Android) | Sensor ~$/mo via Rx; **$0 bridge** (reuse phone) | **Clean** — xDrip reads sensor on-device, can run cloud-free | xDrip → local Nightscout REST on NAS → nudge engine reads on-box |
| **FreeStyle Libre 3/3+ → Juggluco (local offline)** | High — Juggluco captures sensor **offline, no root, no cloud** | Medium-High (Juggluco is finicky; sensor takeover after start) | Sensor via Rx; **$0 bridge** | **Cleanest Libre path** — Juggluco webserver `http://127.0.0.1:17580` serves locally | Juggluco → local Nightscout, or xDrip as "Nightscout Follower" of localhost |
| **Dexcom (any) → HA "Dexcom" integration** | High data, but… | Light | $0 | **VIOLATION** — Cloud Polling against Dexcom Share servers | Reaches HA but PHI already left home. **Flag.** |
| **Libre → LibreLinkUp → Nightscout** | High data | Light | $0 | **VIOLATION** — routes through Abbott cloud (LibreLinkUp/LibreView) | Works but firewall breach. **Flag.** |
| **Self-hosted Nightscout (Docker on NAS)** | The local hub everything feeds | Medium (Docker + Mongo on Synology) | **$0** (own server, no per-seat fees) | **Clean** — "data stays on your servers, no third-party access" | The on-box datastore; HA Nightscout integration = local polling; nudge engine queries REST |
| **Contour Next One (BT fingerstick)** | Moderate — spot checks, elderly-friendly big display, SmartLIGHT in-range color | **Light — plug-and-play meter** | ~$20–35 meter + strips | Meter works standalone; BT sync normally wants Contour app/cloud — **read locally via open tools instead** | Manual log or BT capture into NAS vault; simplest for a 75-yr-old |
| **Medtronic Guardian → CareLink** | High data | Heavy | $$$ | **VIOLATION** — CareLink cloud only, no clean local path | Avoid for LocalDiabetic |

## Honest cloud-lock callouts

- **Libre 3 / 3+ has NO clean direct-BT path in the official app** — it's encrypted and cloud-bound. Juggluco is the *only* solid offline route, and it's a developer-grade setup (sensor takeover, patches). Not plug-and-play for an elderly member without the volunteer.
- **Dexcom Share and LibreLinkUp are convenient and tempting** — they're a one-form HA setup. **They are firewall violations.** Every reading lands on a vendor server. Only fall back to these if the local bridge genuinely can't be stood up, and label it loudly.
- **Medtronic = closed.** CareLink cloud, no community local stack worth shipping.
- **All open-source routes carry the standard disclaimer:** not approved by CGM makers or regulators, use at own risk — fits our *organize/remind/monitor only, never diagnose/dose* doctrine, but the volunteer should set expectations.

## Top picks

- **Top pick — CGM, Dexcom user:** **Dexcom G7 + xDrip+ on a dedicated cheap Android, pushing to self-hosted Nightscout on the NAS.** G7 has native local Bluetooth in xDrip (needs the ≥2026.05.06 build), so readings never need Dexcom's cloud. Cleanest firewall fit with real-time alarms.
- **Top pick — CGM, Libre user:** **Libre 3/3+ + Juggluco (offline mode) → local Nightscout.** The only firewall-clean Libre route. Higher setup lift — assign the paid local volunteer.
- **Top pick — local hub (every member):** **Self-hosted Nightscout in Docker on the Synology NAS**, surfaced to Home Assistant via the **local-polling Nightscout integration**, with the nudge engine reading the on-box REST API. Zero per-seat cost, data never leaves the box.
- **Top pick — elderly / low-vision, light-lift:** **Contour Next One** Bluetooth fingerstick (~$20–35). Big readout, SmartLIGHT in-range color cue, second-chance sampling — genuinely friendly for a 75-year-old. Cheapest, most plug-and-play, real utility for someone not ready for a sideloaded-app CGM rig.

**Architectural rule to enforce:** the Android bridge (xDrip/Juggluco) and Nightscout must be configured cloud-OFF and pointed at the LAN/NAS only. The moment a setup uses Dexcom Share or LibreLinkUp, PHI has left the home and the firewall is breached — that configuration should be refused, not shipped.

Sources:
- [HA Dexcom integration (Cloud Polling, requires Dexcom Share)](https://www.home-assistant.io/integrations/dexcom/)
- [HA Nightscout integration (local polling)](https://www.home-assistant.io/integrations/nightscout/)
- [xDrip Dexcom G7 native local mode](https://navid200.github.io/xDrip/docs/Dexcom/G7.html)
- [Juggluco — offline Libre 1/2/3 capture, no root, local webserver](https://github.com/inxaile/Juggluco/)
- [Juggluco Nightscout/local help](https://www.juggluco.nl/Jugglucohelp/Nightscouthelp.html)
- [Self-hosted Nightscout via Docker (data stays on your server)](https://github.com/t0nn1x/self-hosted-nightscout)
- [Nightscout local implementation (NAS / Pi / HA)](https://nightscout-test.readthedocs.io/en/latest/Nightscout/EN/Technical%20info/local-implementation.html)
- [Contour Next One Bluetooth meter](https://www.ascensiadiabetes.com/products/contour-next-one/)


## Medication Adherence

I have enough to write a thorough, honest section. Here's the research output.

---

# Medication Adherence Devices — LocalDiabetic Category Research

**Doctrine fit reminder:** organize/remind/monitor only — never dose-advise. The dispenser physically holds pills; LocalDiabetic's job is the *nudge layer* around it. The cleanest firewall fit is a **dumb, offline, on-device-alarm dispenser** that LocalDiabetic *wraps* with a local sensor + the Nudge engine — NOT a cloud-monitored "smart" dispenser that phones a vendor.

## The core tension
"Smart" in this category almost always means "calls a vendor cloud and emails the caregiver." That caregiver-alert feature is exactly what LocalDiabetic already does (the Nudge + family safety net) — and the vendor version is a **firewall violation** (dose-event PHI leaves the home). So the winning pattern is: **buy the offline alarm box, skip its cloud, and let the box detect+alert.**

## Comparison table

| Device | Type | Approx cost | Local-first / firewall fit | Install effort | Notes for elderly / LocalDiabetic |
|---|---|---|---|---|---|
| **LiveFine 28-Day Automatic Dispenser** (non-WiFi LCD model) | Auto rotating dispenser, 28 slots, up to 6–9 doses/day, light+sound alarm, key lock | **~$60–90**, no subscription | ✅ **Fully offline.** Programmed on-device LCD. No account. | Light — set time on LCD, load weekly | **Top pick (dispenser).** Big LCD, loud alarm, locking lid (good for confusion/grandkids). Volunteer loads it weekly. Avoid the WiFi/Bluetooth SKUs — same box, adds cloud. |
| **e-pill MedSmart (stand-alone, non-PLUS)** | Locked auto dispenser, tray rotates, light+sound, up to 6/day | **~$430–500** | ✅ Stand-alone version is offline (the **PLUS** version adds cloud text/call alerts = firewall violation) | Light | Medical-grade locking, very senior-proven, but pricey. Buy stand-alone, **never the PLUS/Voice-Pro Bluetooth tier.** |
| **MedQ / AlzStore electronic pill tray** | Manual weekly tray, beeps + lights the next-due compartment | **~$50–70** | ✅ Fully offline, no app ever | Very light | Cheapest "memory-loss" friendly option. No auto-dispense (caregiver pre-loads), just guides which cup. Good for low-complexity regimens. |
| **Hero Health** | Countertop auto-dispenser | $99 + **$30/mo forever** | ❌ **Cloud-locked: bricks if subscription lapses.** Hard firewall violation. | Medium (app setup) | **Do not recommend.** Subscription + mandatory account + dose data to vendor cloud. |
| **MedMinder** | Tablet-style monitored dispenser | **$125/mo** | ❌ Cellular-monitored by design; PHI leaves home | Plug-and-play | **Do not recommend.** Its whole value is the cloud monitoring LocalDiabetic already provides locally. |
| **Pillsy / AdhereTech smart caps** | Bottle cap that beeps/blinks + reports opens | Pillsy ~$40+app; AdhereTech = enterprise/pharma cellular | ⚠️ Cap alarm is local, but adherence data syncs to vendor (AdhereTech is *cellular by design*) | Light | Cap blink/beep is nice, but the data path is cloud. Only usable if you can run it "dumb" (alarm only, ignore app) — Pillsy maybe, AdhereTech no. |
| **DIY: Home Assistant pill reminder** (smart light/Voice PE + Zigbee button/vibration sensor) | Reminder + dismiss + missed-dose escalation | **~$25–60** in parts | ✅✅ **Perfect fit. Zero cloud** (ZHA/Z2M local). | Medium (volunteer + edge box) | **Top pick for integration.** A community HA blueprint already does: light turns on at dose time → press button to dismiss → no-press fires the Nudge. Runs on the Jetson/mini. |

## Top picks

**Best off-the-shelf device (ship-free, volunteer-install):**
👉 **LiveFine 28-Day Automatic Pill Dispenser — the non-WiFi LCD model, ~$60–90, no subscription.** Loud on-device alarm + light + locking lid, all settings on the device, never touches a cloud. Cheap enough to ship free at scale. Crucial: order the **plain LCD SKU, not the WiFi or Bluetooth variant** — same hardware, but those add an account/cloud and become a firewall violation.

**Best LocalDiabetic-native integration (the real moat):**
👉 **DIY Home Assistant reminder loop on the edge box.** A Zigbee/Thread button or vibration sensor on the pill box + a smart light (or the Voice PE speaker), driven by an existing community blueprint: at dose time the light/voice prompts; one button press = "taken" (logged locally, behind the vault); no press within the window = the Nudge engine fires a *generic* off-box nudge to phone/watch and escalates to family. This is the only option where the **dose event stays 100% on the box** and feeds the Nudge directly — no vendor ever sees PHI. Parts ~$25–60, runs on the Jetson/Mac-mini you already ship.

**Recommended combo:** LiveFine (physical dispensing + loud local alarm as the primary, fail-safe layer) **+** a $10 Zigbee vibration/contact sensor on its lid so the box *knows* whether the dose was taken and can run the missed-dose family escalation locally. Best of both: senior-proof hardware alarm, plus a private, on-box adherence signal — no cloud, no subscription, no PHI leaving the house.

## Flags
- **Hero, MedMinder, e-pill PLUS/Voice-Pro, AdhereTech** = cloud/cellular-monitored. Their headline "caregiver alerts" feature is a duplicate of LocalDiabetic's Nudge + family net, delivered via a firewall-violating cloud path. Decline these.
- **Subscription bricking** (Hero) is also a member-harm risk — a free program shouldn't depend on a device that dies if a bill lapses.
- Stay on the right side of doctrine: these devices *remind and hold pills only*. Never let the on-box AI infer "you missed insulin, take X" — that drifts into dosing. The box says "time for your meds" (generic), never *what* or *how much* off-box.

Sources:
- [LiveFine dispensers — official](https://www.livefineproduct.com/collections/pill-dispensers) · [Amazon LiveFine 28-Day](https://www.amazon.com/Live-Fine-Electronic-Medication-Supplements/dp/B08CJMSGMY)
- [Hero pricing ($99 + $29.99/mo, bricks on cancel)](https://herohealth.com/pricing/) · [Senior List Hero review](https://www.theseniorlist.com/medication/dispensers/hero/)
- [MedMinder ($125/mo monitored)](https://shop.medminder.com/product/medminder-pillbox-monthly-monitoring-fee/)
- [e-pill MedSmart (stand-alone vs PLUS-monitored)](https://www.epill.com/medsmart.html)
- [AlzStore MedQ electronic pill tray](https://www.alzstore.com/electronic-reminder-pill-box-dispenser-p/0033.htm)
- [Pillsy smart cap](https://www.pillsy.com/smart-pill-bottle-and-app) · [AdhereTech (cellular, no-app-by-design)](https://www.thedigitalapothecary.com/smart-pill-bottles)
- [Home Assistant pill-reminder blueprint (light + button dismiss, local)](https://community.home-assistant.io/t/pill-reminder-with-light-and-button-press-to-dismiss-suitable-for-voice-pe/851952)
- [Retirement Living — 5 Best Automatic Pill Dispensers 2026 (costs)](https://www.retirementliving.com/automatic-pill-dispensers)


## Foot And Mobility

I have everything I need. Here is the research section.

---

# Diabetic Foot Care & Mobility — Device Research for LocalDiabetic

**Bottom line up front:** The single highest-stakes diabetic device — the foot-temperature mat — is a *firewall problem*, not a hardware problem. The two clinical-grade products (Podimetrics, Siren) are **cloud-locked, nurse-monitored, prescription/subscription services** — they fundamentally violate the firewall (records leave the home, a vendor nurse reads them). For the firewall, the win is a **cheap handheld IR thermometer + a Nudge-engine routine on the box**: the member self-measures, the *reading never leaves the box*, and the Nudge just says "log your feet" / "you flagged a hot spot 2 days running — call Dr. G." That keeps us in doctrine: **monitor + remind, never diagnose.**

## Comparison Table

| Device | Category | ~Cost | Install effort | Local-first / firewall fit | Box integration |
|---|---|---|---|---|---|
| **Handheld IR foot thermometer** (TempTouch-class / generic non-contact IR) | Foot temp | $20–40 generic; TempTouch ~$150 Rx | Light — hand it over, 1 card of instructions | **Perfect.** No radio, no cloud, no account. Member reads 6 points/foot, volunteer logs to vault | Manual log into vault `01-foot-checks/`; Nudge prompts daily + escalates on the 2.2°C / 2-day rule |
| **Podimetrics SmartMat / SmartMat+** | Foot temp mat | Insurance/Rx, no consumer price; service-based | Light hardware, but enrollment-heavy | ❌ **Firewall violation** — cellular mat ships data to Podimetrics cloud + nurse review | None compatible. Flag, don't recommend |
| **Siren Socks** | Foot temp sock | $19.95/mo (~$239/yr), Medicare-covered | Light (wear socks) | ❌ **Firewall violation** — sensors → Siren cloud → licensed-nurse monitoring | None compatible. Flag, don't recommend |
| **Xiaomi Body Composition Scale 2** | Smart scale | ~$48 | Medium — needs ESP32 BLE proxy + ESPHome/Xiaomi-BLE | ✅ **Local-capable.** BLE; with an ESP32 proxy the weight broadcast is captured **on-box, no Mi/Zepp account**. (Native app = cloud; avoid it) | Weight → Home Assistant → vault; Nudge on weight swings (HF/edema signal) |
| **Withings Body** | Smart scale | ~$60–100 | Light to use | ⚠️ **Cloud-forced.** HA integration is OAuth + Withings cloud + public HTTPS webhook. PHI leaves home | Avoid for firewall. Don't recommend |
| **Seeed MR60FDA2** (60GHz mmWave + ESP32-C6) | Fall detection | **~$25** | Light–medium — ceiling/wall mount, pre-flashed ESPHome | ✅ **Excellent.** Ships with ESPHome firmware, **local, no cloud**, no camera (radar = privacy-safe) | Native ESPHome → Home Assistant on edge box; fall event → Nudge → family safety net |
| **Aqara Presence Sensor FP2** | Presence + fall | ~$65–83 | Medium — Wi-Fi, ceiling-mount for fall mode | ✅ **Local.** Automations run on-device/HA, work offline. Fall mode needs ceiling mount | HomeKit-Controller or HA; inactivity + fall → Nudge |
| **Aqara Motion Sensor P1 / Door & Window P2** | Motion / door | ~$20 motion; ~$18–53 door | Light — stick-on, battery (CR2450, ~2 yr) | ✅ **Local via Zigbee** (ZHA/Zigbee2MQTT). ⚠️ Note: Aqara only *officially* supports its own hub; use a standard Zigbee coordinator on the edge box | Zigbee → HA → "no motion by 11am" / "fridge not opened today" living-alone checks → Nudge family |

## Top Picks by Category

**Foot temperature (the highest-stakes one):**
**Generic non-contact IR thermometer (~$20–40) + a LocalDiabetic foot-check routine.** Be honest with the team: we **cannot** ship Podimetrics or Siren — they are nurse-monitored cloud services and break the firewall by design (and Podimetrics has no consumer price; Siren is a $240/yr subscription). Instead we own the doctrine-clean version: member measures 6 plantar points per foot daily, the volunteer or member logs to the vault, and the **Nudge engine applies the published rule as a reminder, not a diagnosis** — "the same spot has been 2°C+ warmer than the other foot for 2 days; time to call your podiatrist." Clinically this is the *same signal* the expensive mats use (early detection prevents up to 75% of ulcers), at ~1% of the cost, with **zero data leaving the house.** If a member wants the validated contact device, TempTouch (~$150, Rx) is the upgrade — still fully local since it just displays a number.

**Fall detection:**
**Seeed MR60FDA2, ~$25.** Cheapest, ships pre-flashed with ESPHome, integrates **natively and locally** into Home Assistant with no cloud and no camera (radar only — ideal for a 75-year-old's bedroom/bathroom, no privacy dread). This is the standout value of the whole category. FP2 (~$70) is the fallback if a member needs multi-zone presence too.

**Smart scale:**
**Xiaomi Body Composition Scale 2, ~$48 + an ESP32 BLE proxy.** Only do this with the ESP32/ESPHome path so the BLE broadcast is caught **on the box with no Mi/Zepp account**. Weight trend is a real diabetic signal (fluid retention / heart-failure early warning, which is exactly what Podimetrics added to SmartMat+). **Explicitly avoid Withings** — its HA integration forces a cloud account and a public webhook, a firewall violation. *Caveat for elderly:* the ESP32 proxy adds setup the volunteer must do; if light-lift matters more than data capture, a plain $15 analog scale + manual Nudge log is the doctrine-safe minimum.

**Living-alone safety (motion/door):**
**Aqara Zigbee motion (P1, ~$20) + door sensors (~$18–20 each)** on a standard Zigbee coordinator (Home Assistant Connect ZBT / SkyConnect) on the edge box — **fully local**, 2-yr batteries, stick-on. Drive "no movement by late morning" and "fridge/front door not opened today" checks into the family safety net via the Nudge. *Watch-out:* Aqara only officially supports its own hub, so commit to ZHA/Zigbee2MQTT on the box (works well in practice, occasional firmware quirks).

## Firewall flags for the team
- 🚩 **Podimetrics SmartMat / SmartMat+** — cellular, cloud + nurse review. Do not ship.
- 🚩 **Siren Socks** — cloud + licensed-nurse monitoring, $240/yr. Do not ship.
- 🚩 **Withings Body** — OAuth/cloud-forced, public HTTPS webhook. Do not ship.
- ⚠️ **Any "smart scale companion app"** (Mi Fit/Zepp, Withings Health Mate) — those apps *are* the cloud leak. Only use the local ESP32/Zigbee capture path.
- ⚠️ **Diagnosis drift:** never let the box say "you have an ulcer." The Nudge applies the published 2.2°C / 2-day temperature-asymmetry *reminder rule* and says "call your clinician." Code it as a reminder threshold, not a verdict.

## Sources
- [Podimetrics SmartMat+ launch (Oct 2025)](https://podimetrics.com/newsevents/podimetrics-an-innovative-company-specializing-in-complex-diabetes-care-has-launched-smartmat/) · [Fierce Healthcare](https://www.fiercehealthcare.com/health-tech/podimetrics-snags-45m-prevent-diabetic-foot-amputations-temperature-detecting-mat)
- [Siren Socks — what it is / nurse monitoring](https://www.siren.care/blog/what-is-siren-diabetic-sock-system) · [Pharmacy Times on smart socks pricing](https://www.pharmacytimes.com/view/smart-socks-are-entering-the-market-for-patients-with-diabetes)
- [Home Monitoring of Foot Skin Temperatures to Prevent Ulceration (ADA, Diabetes Care)](https://diabetesjournals.org/care/article/27/11/2642/23780/Home-Monitoring-of-Foot-Skin-Temperatures-to) · [Low-cost thermal camera diabetic foot framework (MDPI 2026)](https://www.mdpi.com/1424-8220/26/8/2438)
- [TempTouch infrared skin thermometer](https://www.diabetesincontrol.com/temptouchr/)
- [Seeed MR60FDA2 fall sensor ($24.90)](https://www.seeedstudio.com/MR60FDA2-60GHz-mmWave-Sensor-Fall-Detection-Module-p-5946.html) · [ESPHome component](https://esphome.io/components/seeed_mr60fda2/)
- [Aqara FP2 — local automation, fall detection](https://us.aqara.com/products/presence-sensor-fp2) · [FP2 fall detection in Home Assistant (GitHub)](https://github.com/TGSmartHome/Aqara-FP2-Sensor-Fall-detection-in-Home-Assistant)
- [Xiaomi Mi Body Composition Scale 2 → HA via ESP32 BLE bridge](https://github.com/rando-calrissian/esp32_xiaomi_mi_2_hass)
- [Withings HA integration (OAuth/cloud + public webhook)](https://www.home-assistant.io/integrations/withings/)
- [Zigbee + Home Assistant local-first guide](https://secureiot.house/open-source-home-automation-zigbee-home-assistant-guide-2026/) · [Best Zigbee sensors for HA](https://raspberry.tips/en/smart-home/zigbee-sensors-home-assistant)


## Vitals Wearables

I have enough verified data to write the section. Here's the research output.

---

# Vitals & Wearables — Local-First Research for LocalDiabetic

**Doctrine reminder:** organize / remind / monitor only — these devices feed numbers into the vault; the box never diagnoses or doses. The hard test below is **the firewall**: does the reading land on the member's box without first being forced through a vendor cloud?

## The one big finding

Almost every "smart" health device on the shelf is **cloud-first by default** (Omron Connect, Withings Health Mate, Mi Fit/Zepp all want an account and ship your readings to their servers). But several of them **also broadcast or store the raw reading over Bluetooth**, and a small Home Assistant / ESPHome ecosystem has learned to **intercept that BLE data locally before it ever reaches the vendor app**. That's the seam LocalDiabetic lives in: buy popular, reliable, FDA-cleared hardware, then read it locally via HA on the edge box and **never install the vendor cloud app at all**.

The clean pattern: **device → BLE → ESP32 Bluetooth-proxy (or the edge box's own BT) → Home Assistant on the Jetson/Mac-mini → the Nudge engine.** No vendor account, firewall intact.

## Comparison table

| Category | Device (model) | ~Cost | Local-first path | Firewall fit | Install effort | Elderly fit |
|---|---|---|---|---|---|---|
| **BP cuff** | **Omron 10-Series / Evolv** (BP7450, BP7000; HEM-7xxx intl.) | $58–105 | `hass-omron` HA integration polls device EEPROM over BLE every ~5 min — **fully local, no Omron account** | ✅ **Strong** — but device pairs to ONE host; must NOT pair the Omron Connect app | Light–medium (one-time HA pairing by volunteer) | Good — big display, one-button, #1 doctor-recommended |
| **BP cuff (display-only)** | Greater Goods Pro-Series / Balance | $40–60 | BLE present, but no clean local-read integration today; **best used as a plain big-number cuff, member keys reading into the vault** | ⚠️ Cloud app exists; skip the app, use offline | Lightest (no pairing) | **Excellent** — oversized inverted backlit LCD, no glasses needed |
| **BP cuff** | Withings BPM Connect | ~$100 | Requires Withings account + Health Mate app; HA "Withings" integration is **cloud-polled (OAuth to Withings servers)** | ❌ **Firewall violation** — data transits Withings cloud | Light | Good but disqualified |
| **Pulse oximeter** | **CONTEC PC-60FW** (fingertip BLE) | ~$45–60 | **ESPHome config reads SpO2 / pulse / perfusion locally** via ESP32 — proven community config | ✅ **Strong** — never needs the CONTEC app | Medium (ESP32 flash, one-time by volunteer) | Good — standard fingertip clip; reading also shows on its own screen |
| **Pulse oximeter (simple)** | Any non-connected fingertip oximeter | $15–25 | No data link — member reads number, keys it into vault | ✅ Trivially private (air-gapped) | Lightest | Excellent — cheapest real utility |
| **Smart scale** | **Xiaomi Mi Body Composition Scale 2** | ~$25–35 | **ESPHome / BLE-monitor reads weight + impedance locally** (`bodymiscale`); data diverted from Mi Fit | ✅ **Strong** — no Xiaomi account if read via HA | Medium (ESP32 + body-metrics component) | Good — step-on, no buttons; big number on glass |
| **Smart scale** | Withings Body / S-series | $100+ | Cloud-bound like BPM Connect | ❌ Cloud-forced | Light | Disqualified |
| **Wearable** | **Apple Watch** (+ iPhone) | $250–400 + phone | **"Health Assistant Link" app pushes HealthKit data iPhone→HA directly, no third-party cloud**; HealthKit itself is a local on-phone store | ✅ **Good** (data path stays phone→box) — but pricey, iPhone-dependent, fiddly | Heavy (Apple ID, app, watch setup) | Poor for a 75-yo low-vision member; tiny screen, charging burden |

## Top picks per category

- **Blood-pressure cuff → Omron 10-Series (BP7450) read via the `hass-omron` integration.** This is the standout: a mass-market, FDA-cleared, doctor-recommended cuff with a large display **and** a maintained open-source HA integration that pulls readings straight off the device's memory over Bluetooth with **zero Omron cloud**. The one gotcha to brief the volunteer: pair it to the box only — do **not** install Omron Connect, since the device allows just one paired host. If you want the absolute lightest lift for a very-low-vision member, pair it with a **Greater Goods** cuff used purely for its oversized backlit numbers (member reads, keys in).

- **Pulse oximeter → CONTEC PC-60FW for the connected path (proven ESPHome local read), or a $15–25 dumb fingertip clip for the air-gapped path.** Honest call: for most elderly members the **$20 non-connected oximeter is the better real-world choice** — zero setup, zero firewall surface, and the SpO2 number is what matters. Reserve the PC-60FW for members where continuous logging earns its keep.

- **Smart scale → Xiaomi Mi Body Composition Scale 2** read locally via ESPHome/`bodymiscale`. ~$30, step-on-and-go, and the BLE-intercept story is the most mature of any scale. Weight trend is genuine diabetic-life utility (fluid, foot-offloading recovery, meds). Avoid Withings scales — cloud-forced.

- **Wearable → hold, don't lead.** Apple Watch *can* stay firewall-clean (HealthKit is local; "Health Assistant Link" pushes phone→HA with no third-party server), but it's expensive, iPhone-tethered, and a heavy setup with a tiny screen — wrong fit for the 75-yo flagship member. Recommend wearables only for younger/tech-comfortable members who already own the hardware.

## Flags (be honest)

- **❌ Withings (BPM Connect + Body scales):** HA integration is cloud-OAuth-polled; data provably transits Withings servers. **Firewall violation — do not recommend** despite great hardware.
- **⚠️ The "install the vendor app" trap:** Omron Connect, Mi Fit/Zepp, Health Mate all default to cloud. The local-first benefit **only holds if the volunteer never installs the vendor app** and pairs the device directly to the box. Bake this into the volunteer setup checklist.
- **⚠️ Single-pairing on Omron:** device bonds to one host. If a member previously used Omron Connect, the volunteer must un-pair the phone first.
- **⚠️ Drift-toward-diagnosis watch:** several "for seniors" monitors advertise AFib detection / hypertension color zones. The box may **log and nudge** ("BP logged — reminder to share with Dr. G"), but must **never** surface an interpretation as a verdict. Keep AFib/zone flags as raw device output, not LocalDiabetic output.

## How it plugs into the box

Add a **~$10–15 ESP32 flashed as a Bluetooth proxy** placed near where the member takes readings; it relays BLE to **Home Assistant running on the Jetson/Mac-mini edge box**. HA writes the reading into the vault (the `00–15` folder structure), and the **Nudge engine fires a generic off-box reminder** ("morning BP reading is due" / "new reading saved") while the actual numbers stay behind the `vault_ref` pointer — consistent with the P2 nudge design already live on the NAS. Net added BOM per member for full local vitals: roughly **cuff $60 + scale $30 + oximeter $20 + ESP32 $15 ≈ $125**, all shippable, all set up once by the paid local volunteer.

Sources:
- [hass-omron (local BLE integration, supported HEM-7xxx models)](https://github.com/eigger/hass-omron)
- [Omron Evolv BP7000 / 10-Series BP7450 pricing](https://omronhealthcare.com/products/evolv-wireless-upper-arm-blood-pressure-monitor-bp7000)
- [ESPHome config for CONTEC PC-60FW oximeter (local SpO2/pulse)](https://community.home-assistant.io/t/esphome-configuration-for-contec-pc-60fw-bluetooth-pulse-oximeter/969609)
- [Xiaomi Mi Scale 2 local via ESPHome / bodymiscale](https://github.com/dckiller51/bodymiscale)
- [Withings BPM Connect requires Withings account](https://support.withings.com/hc/en-us/articles/360024317614-BPM-Connect-No-data-is-synced-with-my-account-What-should-I-do)
- [Withings HA integration is cloud-reachable/OAuth](https://www.home-assistant.io/integrations/withings/)
- [Apple Health → Home Assistant local (Health Assistant Link, no cloud)](https://apps.apple.com/us/app/health-assistant-link/id6745420767)
- [Greater Goods large-backlit BP monitors](https://shop.greatergoods.com/products/greater-goods-smart-pro-series-blood-pressure-monitor-bluetooth-upper-arm-smart-bpm-with-large-backlit-lcd-premium-hardware)
- [Best BP monitors for seniors / big-display](https://allseniors.org/articles/top-smart-blood-pressure-monitors-and-pulse-oximeters-for-seniors-in-2025/)


## Home Safety Environment

I have comprehensive, current data. Here's the research section.

---

# Home Safety & Environment Devices for LocalDiabetic

## The firewall unlock (read this first)

The single most important finding: **put one Sonoff ZBDongle-E (~$20–30) USB Zigbee coordinator on the LocalDiabetic edge box (Jetson/Mac-mini) running Zigbee2MQTT or ZHA inside Home Assistant.** This makes *every* device below run **100% local — no Aqara hub, no vendor cloud, no account, no internet.** Sensor readings hit the edge box directly over the Zigbee mesh and feed the Nudge engine. This is a clean firewall fit: PHI-adjacent data (fridge temp, "I took my meds" press, bed-occupancy at night) stays on the box; only a generic nudge goes off-box.

**Avoid the trap:** buying these same devices with the manufacturer's own hub (Aqara M2/E1, Tuya gateway, SmartThings) routes data through a vendor cloud and usually forces an account = firewall violation. Same physical sensor, opposite privacy outcome. **Always pair the bare Zigbee coordinator, never the brand hub.** (Wi-Fi/Tuya-cloud versions of these plugs/sensors exist and are cloud-forced — skip them; buy the Zigbee SKU.)

A Zigbee mesh also self-heals: every mains-powered smart plug acts as a repeater, extending range for the battery sensors — good for an elderly member's larger/older home.

## Comparison table

| Device | Category | Approx cost | Install effort | Firewall fit (with ZBDongle-E + Z2M) | LocalDiabetic utility |
|---|---|---|---|---|---|
| **Zigbee temp sensor w/ external waterproof probe** (generic Tuya Zigbee, -40→125°C) | Insulin fridge/freezer monitor | ~$15–20 | Light — probe inside fridge, body outside, magnet/tape | Local-first ✅ (Zigbee, no cloud) | **Highest.** Insulin spoils >30°C and if frozen. Probe reads the actual interior; Nudge fires "check the fridge" on threshold breach. Power-outage = fridge warms = caught. |
| **Sonoff SNZB-02P** (temp/humidity, no probe) | Room/fridge-door temp | ~$10–13 | Plug-and-play, pairs <1 min | Local-first ✅ | Good for ambient/medicine-cabinet temp; ±0.2°C, 4-yr battery. No probe so less ideal *inside* a closed fridge. |
| **Aqara Wireless Mini Switch (WXKG11LM)** | Smart button — "I need help" / "I took my meds" | ~$15–20 | Light — stick on wall/nightstand | Local-first ✅ *if* paired to ZBDongle-E, **not** the Aqara hub | **Top button.** Single/double/long-press = three actions (e.g. press = "took meds" log; long-press = "I need help" → family safety net). No screen, big tactile press — elderly/low-vision friendly. |
| **Sonoff SNZB-04P** (door/window contact) | Door/cabinet/med-fridge open sensor | ~$13.50 | Peel-and-stick magnet pair | Local-first ✅ | Med-cabinet "did they open it today?" → if not opened by noon, Nudge fires. Also front-door safety (wandering, or "left and didn't return"). 5-yr battery. |
| **Zigbee under-mattress pressure mat / bed-occupancy sensor** | Bed/night safety | ~$25–40 | Medium — runs under mattress | Local-first ✅ | "Out of bed at 3am and not back in 20 min" → family nudge. Honest: pressure mats need enough body weight through the mattress; placement-sensitive. |
| **Sonoff S40 Lite Zigbee smart plug** (on/off, repeater) | Smart plug + mesh repeater | <$10 | Plug-in, pairs <45s | Local-first ✅ | Schedule a light/lamp; mesh repeater strengthens the whole sensor network. No energy metering. |
| **ThirdReality Zigbee Smart Plug Gen2 (power metering)** | Smart plug w/ energy monitor | ~$15–19 (4-pk ~$77) | Plug-in | Local-first ✅ | Energy draw on the *fridge plug* = a free power-outage / fridge-died alarm (watts drop to 0). Doubles as repeater. |
| **ThirdReality Zigbee water leak sensor (4-pk, 120dB)** | Leak/flood under sink, water heater | ~$50/4-pack (~$12.50 ea) | Drop on floor | Local-first ✅ | Home-safety baseline; protects a member who can't easily get down to mop or react fast. Loud local siren + Nudge. |
| ⚠️ **Aqara Presence Sensor FP2** (mmWave, fall detection) | Fall detection | ~$60–80 | Medium — wired USB-C, needs aiming/zones | ⚠️ **Cloud-forced / 2.4GHz Wi-Fi required**; "fall detection" drifts toward diagnosis | **Flagged, not recommended.** Wi-Fi to Aqara cloud = firewall violation, and its fall-detection feature crosses the monitor-not-diagnose line. If ever used, must be the local-API path only and positioned as "movement," never medical. |

## Top picks per category

- **Insulin fridge monitor (the marquee device):** **Generic Zigbee temp sensor with external waterproof probe (~$15–20).** Probe goes *inside* the fridge where insulin actually sits; body stays outside for radio. This is the highest-real-utility device in the whole category — heat or freeze ruins insulin and a power blip can do it silently. Pair with a **ThirdReality power-metering plug on the fridge** as a redundant "fridge lost power" signal.
- **Smart button ("help" / "took my meds"):** **Aqara Wireless Mini Switch (~$15–20), paired to the ZBDongle-E (never the Aqara hub).** One big press, three programmable actions, no screen — ideal for a 75-year-old.
- **Door/med-cabinet:** **Sonoff SNZB-04P (~$13.50).**
- **Smart plug:** **Sonoff S40 Lite (<$10)** for on/off + repeater; **ThirdReality Gen2 (~$15)** when you want the fridge-power alarm.
- **Leak:** **ThirdReality 4-pack (~$50).**
- **Coordinator (buy once per home, the enabler):** **Sonoff ZBDongle-E (~$20–30)** on the edge box. This is what keeps the whole kit behind the firewall.

## Honest flags
- **Cloud-lock-in:** Aqara/Tuya/SmartThings **hubs** and all **Wi-Fi "smart" variants** force vendor cloud + accounts → buy the **Zigbee** SKU + bare coordinator instead. The Aqara *FP2* specifically requires Wi-Fi to Aqara's cloud — flagged.
- **Diagnosis drift:** mmWave "fall detection" (FP2) and any sensor marketed for "health/vitals" crosses the monitor-only doctrine. Keep everything framed as environment/movement/contact monitoring that fires a generic Nudge — never an interpretation.
- **Light-lift reality:** probe placement, mmWave aiming, and bed mats are the only "medium" installs; everything else is peel-and-stick / plug-in, which suits the paid-local-volunteer setup model. Initial Zigbee pairing is the one task that needs the volunteer or a remote hand.
- **Real cost of a starter kit per home:** ~$30 coordinator + ~$20 fridge probe + ~$18 button + ~$14 door sensor + ~$15 fridge-power plug ≈ **~$95–110 in hardware** for a meaningful insulin-safety + meds + help-button bundle, all local-first.

Sources:
- [Sonoff SNZB-02P / temp-humidity guide](https://sonoff.tech/en-us/blogs/news/home-assistant-temperature-humidity-sensor-setup-and-automation-guide)
- [ThirdReality Zigbee temp sensors (pricing)](https://slickdeals.net/f/19029670-thirdreality-zigbee-temperature-and-humidity-sensor-lite-smart-thermometer-and-hygrometer-hub-required-14-99)
- [Zigbee temp sensor w/ external waterproof probe](https://www.amazon.com/ZigBee-Temperature-Sensor-External-Waterproof/dp/B0CBCZGC62) · [freezer/probe overview](https://www.zigbeedevice.com/zigbee-temperature-sensors-with-probe-reliable-monitoring-for-freezers-pipes-and-water-systems/)
- [Aqara Wireless Mini Switch (Z2M local)](https://spicehometech.com/device/wireless-mini-switch/)
- [Sonoff SNZB-04P door/window sensor ($13.50)](https://itead.cc/product/sonoff-zigbee-door-window-sensor-snzb-04p/) · [Zigbee gadgets under $15](https://www.xda-developers.com/zigbee-gadgets-under-15-that-massively-improved-my-smart-home/)
- [Sonoff S40 Lite Zigbee plug / best plug 2026](https://homeappliancepicks.com/smart-home/best-zigbee-smart-plug-for-home-assistant/) · [ThirdReality Smart Plug Gen2 power metering](https://www.thirdreality.com/products/smart-plug-gen2-power-metering)
- [ThirdReality Zigbee water leak sensor 4-pack](https://slickdeals.net/f/18440047-thirdreality-zigbee-water-leak-sensor-with-dripping-detection-4-pack-120-db-alarm-app-notifications-enabled-when-compatible-with-home-assistant-and-compatible-zigbee-hub-49-99)
- [Zigbee bed/pressure occupancy sensor](https://community.home-assistant.io/t/configurable-zigbee-bed-presence-occupancy-sensor/433951) · [Aqara FP2 (Wi-Fi/cloud, fall detection)](https://www.amazon.com/Aqara-Positioning-Multi-Person-Detection-Assistant/dp/B0BXWZMQJ3)
- [Make Aqara devices 100% local / skip the hub](https://forum.aqara.com/t/how-to-make-aqara-devices-work-100-locally-no-cloud-access-required/118283) · [Zigbee2MQTT no-cloud setup](https://smart-wired.com/home-assistant/zigbee2mqtt-setup/)
- [Sonoff ZBDongle-E coordinator (best value 2026)](https://smarthomescene.com/top-picks/best-zigbee-coordinators-for-home-assistant/)


## Voice Accessibility

I have enough to write a tight, honest section. The American Lifetime clocks typically run ~$40-70; I'll note that range. Here's the research output.

---

# Voice & Accessibility — Local-First for LocalDiabetic

The firewall makes this category unusually clean-cut: **the two mass-market "obvious" picks (Amazon Echo Show, Google Nest Hub) are firewall violations** — both force every voice request and reminder through a vendor cloud, with no local-only mode. They are explicitly *not recommended*. The good news: there is now a genuine, cheap, local-first voice stack that runs **on the box we already ship** (Synology NAS + Jetson/Mac-mini edge), plus a class of dumb-but-perfect big-display reminder clocks that never touch the internet at all.

## How this plugs into the LocalDiabetic box
- **HA Voice / Wyoming satellites** are the firewall-correct answer: the speaker is a thin ESP32 mic/speaker; **Whisper (speech-to-text), Piper (text-to-speech), openWakeWord, and even a local LLM (Ollama) all run on the member's own edge box** — no cloud, no recordings leaving the house. This is a direct fit for the Jetson/Mac-mini already in the architecture. Home Assistant runs on the NAS or edge box; the Nudge engine can fire spoken reminders through the satellite and accept hands-free "I took it" check-ins, all on-LAN.
- **Big-display dementia/medication clocks** are fully offline appliances — no network at all. They don't integrate with the box electronically, but they're the lowest-lift, highest-utility accessibility device for a 75-year-old and carry **zero firewall risk by construction**.

## Comparison

| Device | Category | Approx cost | Install effort | Privacy / firewall fit | Box integration |
|---|---|---|---|---|---|
| **Home Assistant Voice Preview Edition** | Local voice assistant | **$59** | Medium (needs HA + Whisper/Piper on edge box) | ✅ **Fully local** — STT/TTS/LLM on member's box, nothing to cloud | Native; built by HA founders; pairs with Jetson/NAS + Nudge |
| **ESP32-S3-BOX-3 / M5 ATOM Echo (Wyoming satellite)** | DIY local voice satellite | ~$15–55 | High (flash + configure) | ✅ Fully local via Wyoming | Same stack as HA Voice, cheaper/hackier; needs a volunteer to flash |
| **ESPHome wall panel / e-ink dashboard** (e.g. CrowPanel, Guition, Seeed e-ink) | Big local display | ~$30–90 | Medium–High | ✅ Local LAN only; no vendor cloud | Renders HA dashboard + Nudge to-dos on-wall |
| **American Lifetime / KASTISS / ORKA dementia day-clock** | Big-button offline reminder clock | **~$40–70** | ✅ **Light-lift** (plug in, set alarms) | ✅ **No network at all** — zero risk | None (standalone), but complements the box |
| **GrandPad** | Senior tablet | $250 + **$25/mo or ~$275/yr** | Light | ❌ **Cloud-locked** — closed vendor network, carrier-locked, subscription | ❌ Does not integrate; recurring cost breaks the "free to member" model |
| ~~Amazon Echo Show~~ | Smart display | $90–150 | Light | ❌ **FIREWALL VIOLATION** — cloud-only voice, recordings to Amazon | ❌ Not recommended |
| ~~Google Nest Hub~~ | Smart display | $60–100 | Light | ❌ **FIREWALL VIOLATION** — no local voice; all requests to Google cloud | ❌ Not recommended |

## Top picks

**Top pick — local voice / hands-free: Home Assistant Voice Preview Edition ($59).** It is the only mainstream off-the-shelf voice device that runs **fully local on hardware we already ship**, built by Nabu Casa (the HA team) explicitly as the open, private alternative to Alexa/Siri. Whisper + Piper + Ollama on the Jetson/edge box means a member can say a reminder or do a hands-free "I took my insulin" check-in and **no audio ever leaves the home** — a perfect firewall fit. Main cost is install effort (a local volunteer sets up HA + the voice pipeline once); after that it's plug-and-play for the member. *Doctrine guardrail: scope the on-box LLM to organize/remind/check-in language only — never let it answer dosing or "is this number bad" questions.*

**Top pick — accessibility / lowest-lift: a big-display dementia day-clock (~$40–70, e.g. American Lifetime 2026, KASTISS, ORKA Talking Clock).** For a low-vision 75-year-old this is the single highest utility-per-dollar device in the whole category: 12–15" high-contrast display, spells out full day/date/time-of-day with no abbreviations, readable from ~20 ft, 3+ programmable medication alarms (ORKA even does recordable voice prompts), battery backup. **Plug in and set — no app, no account, no network, zero firewall risk.** It doesn't talk to the box, but it's the device a volunteer can have working in five minutes and it never breaks the "free to member" rule.

**Avoid:** Echo Show and Nest Hub (cloud-forced voice = firewall violations) and GrandPad (cloud-locked + a recurring $25/mo subscription that conflicts with the free-to-member, no-strings model).

Sources:
- [Home Assistant Voice Preview Edition (official, $59)](https://www.home-assistant.io/voice-pe/)
- [Building the AI-powered local smart home — Ollama on HA](https://www.home-assistant.io/blog/2025/09/11/ai-in-home-assistant/)
- [HA approach to wake words / Wyoming satellites](https://www.home-assistant.io/voice_control/about_wake_word/)
- [Best Home Assistant Voice Satellites 2026 (Alexa-free, fully local)](https://www.smarthomeexplorer.com/guides/best-home-assistant-voice-satellite-2026)
- [Echo Show vs Google Nest Hub — privacy/cloud, elderly](https://www.seniortechchoice.com/blog/comparisons/echo-show-vs-google-nest-hub/)
- [GrandPad review & 2026 pricing (subscription)](https://www.seniorliving.org/cell-phone/consumer-cellular/grandpad/)
- [American Lifetime 2026 Dementia Day Clock (Amazon)](https://www.amazon.com/American-Lifetime-Dementia-Digital-Seniors/dp/B0CST7VFKV)
- [ORKA Talking Medication Reminder Clock (Amazon)](https://www.amazon.com/ORKA-Recordable-Dementia-Medication-Reminder/dp/B07NP6JP5P)
- [ESPHome wall-panel dashboards for HA](https://3zebras.com/news/how-to-create-wall-mounted-smart-home-panel-with-esphome-and-home-assistant/14408/)


## Hub Connectivity

I have all I need. Here is the research section.

---

# LocalDiabetic — Hub & Connectivity Layer Research

**The glue question:** how do cheap, light-lift home sensors talk to the LocalDiabetic box *without* any data leaving the house? The answer is a **local-first protocol stack (Zigbee / Thread / Matter) + Home Assistant + a single one-line webhook into the Nudge engine.** Done right, the firewall holds by design: the radios and the automation brain both live on the member's own box, and the only thing that ever crosses the boundary is the same generic, non-PHI nudge you already ship.

## How it fits the box (the architecture)

```
[Zigbee/Thread/Matter sensors]  →  [USB radio coordinator]  →  [Home Assistant on NAS/edge]
   pill cap, door, motion,            ZBT-2 / Sonoff dongle      (Container Manager docker
   bed mat, button, leak                                          on Synology, OR on Jetson/
                                                                  Mac-mini edge box)
                                                                          │
                                              local automation fires a POST (rest_command)
                                                                          ▼
                                            [LocalDiabetic Nudge engine  ld_remind.py]
                                              → generic non-PHI nudge → ntfy → phone/watch
```

- **HA runs ON the box you already ship.** Home Assistant Container is fully supported in 2026 on Synology Container Manager (Intel DS220+/720+/920+ class, DSM 7+, ~200–400 MB RAM idle — trivial alongside the vault). It also runs natively on the Jetson/Mac-mini edge box. So **no new hardware is required for the brain** — only a small USB radio.
- **The webhook is one line.** An HA automation triggers a `rest_command` POST to a localhost endpoint on the Nudge engine (`{{ trigger.json }}` carries the event). Keep HA webhooks set `local_only: true` and the POST target on 127.0.0.1 / LAN — nothing routes out. This is the clean integration seam with the existing `engine/ld_remind.py`: HA does the *sensing/automation*, the Nudge does the *generic off-box alert*. PHI (which sensor, what reading) stays in HA on the box; only a generic `vault_ref`-style nudge goes to the phone — exactly the existing doctrine.

## Comparison — coordinators & hubs

| Device | Role | ~Cost | Install effort | Privacy / firewall fit | Box integration |
|---|---|---|---|---|---|
| **Sonoff ZBDongle-E (EFR32MG21)** | Zigbee USB coordinator | **$17–20** | Light — plug into NAS/edge USB, pick ZHA | ✅ 100% local, no account, no cloud ever | Native HA ZHA. Best $/device. |
| **HA Connect ZBT-2** | Zigbee **or** Thread USB radio (official) | **$49** | Light — plug in, HA auto-detects | ✅ 100% local, made by Open Home Foundation | Native HA. Adds Thread/Matter-over-Thread. Note: **one protocol at a time** (Zigbee *or* Thread, not both — buy two if you need both). |
| **Aqara Hub M100** | Matter bridge + Thread Border Router (USB-stick) | **$30** | Light — USB power, QR pair, ~3 min | ⚠️ Mixed: local automation works, but Aqara's own pairing/app leans on Aqara cloud account; the Matter-bridge half is buggy. Use it as a *Thread border router exposed to HA via Matter*, not via the Aqara cloud. | Works, but adds a vendor-cloud dependency for setup — **flag**. |
| **Aqara Hub M3 / M200** | Premium Matter+Zigbee+Thread, PoE, local automation | **$90–120** | Medium | ⚠️ Same Aqara-account caveat as M100 | Overkill + vendor lock for this use case. Skip. |
| **Home Assistant Green** | Standalone HA appliance (if NOT using NAS/edge) | **$159** | Light (turnkey box) | ✅ Local-first | **No built-in radio** anymore — still needs a ZBT-2/Sonoff dongle. Only buy if a member has no NAS/edge box to host HA. |
| **HA Yellow** | (discontinued) | — | — | — | Dead — do not source. |
| **Apple HomePod mini** | Thread border router + Matter controller | ~$99 | Light | ❌ Requires Apple ID / iCloud; automations live in Apple Home cloud | **Firewall violation** for our purposes — pushes routing/automation toward Apple's cloud. Do not recommend as the LocalDiabetic brain. |

## Cloud-lock / drift flags

- **Apple Home / Google Home / Alexa / SmartThings as the *brain* = firewall violation.** They require a vendor account and run automation logic in the vendor cloud. We can let a Matter device *also* appear in Apple Home for the member's convenience, but **HA on-box must be the source of truth** that triggers the nudge. Never route the safety automation through a cloud assistant.
- **Aqara hubs:** the radio is fine and local, but setup/pairing drags in an Aqara account. If used, treat it purely as a dumb Thread border router surfaced to HA over Matter, and document the residual cloud touch. Prefer the Open Home / Sonoff dongles to avoid it entirely.
- **No diagnosis drift here** — this layer is pure plumbing (sense → automate → generic nudge). It must stay that way: HA automations should fire neutral events ("no pill-cap open by 9am") and let the Nudge engine emit the generic reminder; never let HA compute or display a clinical interpretation.

## Top picks

**🏆 Cheapest light-lift path (default ship):**
**Sonoff ZBDongle-E ($17–20) plugged into the NAS or edge box, running Home Assistant in Container Manager / docker.**
Total added hardware cost: **~$20.** It's 100% local, no account, no cloud, officially HA-supported, and reuses the box the member already has. Pair it with cheap Zigbee sensors (pill-cap/door/motion/button/bed-mat — covered in the sensor category) and wire one `rest_command` POST into `ld_remind.py`. This is the firewall-cleanest and cheapest possible glue.

**🏆 If the member needs Thread/Matter devices too:**
**Home Assistant Connect ZBT-2 ($49)** — same plug-into-the-box story, official Open Home hardware, fully local, and future-proofs to Matter-over-Thread. One caveat: it does Zigbee *or* Thread at a time, so if a member's kit mixes both, ship a ZBDongle-E **and** a ZBT-2 (~$67 total, still cheap) rather than fighting MultiPAN.

**🏆 Only if there is NO NAS/edge box to host HA:**
**Home Assistant Green ($159) + a $20 Sonoff dongle** — a turnkey local hub. Avoid for members who already have the Synology/Jetson/Mac-mini, since HA runs on that for free.

**Volunteer setup note:** all three winners are "plug the USB stick in, HA discovers it" — well within a paid local volunteer's reach, no member interaction needed. The member never logs into anything; the elderly/low-vision member only ever sees the big-button ntfy nudge on their phone, unchanged from today.

**Sources:**
- [Home Assistant Connect ZBT-2 launch ($49) — CNX Software](https://www.cnx-software.com/2025/11/20/home-assistant-connect-zbt-2-zigbee-thread-usb-adapter/)
- [Connect ZBT-2 — Home Assistant official](https://www.home-assistant.io/connect/zbt-2/)
- [Best Zigbee Coordinators for Home Assistant 2026 — SmartHomeScene](https://smarthomescene.com/top-picks/best-zigbee-coordinators-for-home-assistant/)
- [SONOFF ZBDongle-E product page](https://sonoff.tech/en-us/products/sonoff-zigbee-3-0-usb-dongle-plus-zbdongle-e)
- [Best Smart Home Hubs 2026 — The Gadgeteer](https://the-gadgeteer.com/2026/06/13/best-smart-home-hubs-2026/)
- [Best Thread Border Routers June 2026 — ACFC](https://acfc.org/best-thread-border-routers/)
- [Aqara Hub M100 review — Matter Alpha](https://www.matteralpha.com/review/aqara-hub-m100-review-best-value-matter-hub)
- [Install Home Assistant on Synology NAS with Docker (2026) — Ben Abt](https://benjamin-abt.com/blog/2025/12/27/install-home-assistant-on-synology-with-docker/)
- [Home Assistant on Synology NAS Complete Guide 2026 — HomeShift](https://joinhomeshift.com/home-assistant-synology)
- [Home Assistant RESTful Command integration](https://www.home-assistant.io/integrations/rest_command/)
- [Home Assistant Automation triggers (webhook, local_only)](https://www.home-assistant.io/docs/automation/trigger/)
- [Home Assistant Green requires external Thread/Zigbee adapter — Seeed Studio](https://www.seeedstudio.com/blog/2025/07/23/does-home-assistant-green-support-zigbee-and-thread-devices/)



---

# Red-Team Review

I reviewed the plan against the firewall (no PHI leaves the box), the monitor-not-diagnose doctrine, and real shipping-product reality. It is mostly disciplined and on-brand. Below are the specific flags, then a prioritized fix list.

---

## (a) Devices that FORCE data to a vendor cloud but are presented as local

1. **Sonoff SNZB-04P — wrong battery claim, not a firewall issue but a factual one (see (d)). Local: OK.** No cloud flag.

2. **Aqara Mini Switch / Aqara Motion P1 / Aqara contact (Starter + menu).** Correctly flagged to pair to the ZBDongle-E, never the Aqara hub. This is right — but the plan should state the *hard caveat* that **some Aqara SKUs (notably certain P-series and FP sensors) only expose full functionality via the Aqara hub** and degrade or won't pair cleanly to a generic Zigbee coordinator. As written it implies all Aqara gear is hub-free behind our dongle. Mostly local, but verify per-SKU.

3. **Dexcom G7 → xDrip+ → Nightscout listed under "Better" as "$0 bridge."** This is the biggest soft spot. xDrip+ reads the G7 **locally over BLE only if** the phone is the *primary* collector and the official Dexcom app is not co-collecting. In practice on G7, many users are forced through the Dexcom app / Share path, and the reliable local route often requires a specific build + a "native mode" workaround that breaks across firmware updates. Calling this "$0 bridge, plug-in" under "Better" oversells it — it belongs at the same dev-grade tier as Juggluco, not a tier above the Contour fingerstick. **Not mislabeled-local (the data genuinely stays local when it works), but mislabeled as light-lift.** See (c).

4. **HA "Dexcom" integration correctly identified as cloud-polling in the Avoid list.** Good — this is accurate and well-caught.

5. **Matter "also appears in Apple/Google Home for convenience."** This is the one genuine latent firewall crack in the spine. The moment a Matter device is commissioned into Apple/Google Home, **its state is mirrored to that vendor's cloud** even if your safety automation runs locally in HA. The plan says automations won't route through the cloud assistant, but it does not acknowledge that *commissioning into that ecosystem at all* puts device-state telemetry (e.g., "door opened," "button pressed") on a vendor server. For a PHI-adjacent device (med-cabinet door, help button) that is arguably a firewall violation. **Flag: either keep safety-relevant devices HA-only, or explicitly accept and log this as a non-PHI-but-device-state leak.**

## (b) Drift toward DIAGNOSIS rather than monitor/remind

6. **Play 2 foot-temp — the "2°C+ warmer for 2 days → call Dr. G" rule.** This is the closest the whole plan comes to the diagnosis line. The framing ("apply the published rule as a reminder, not a verdict," "call your clinician, never 'you have an ulcer'") is doctrinally correct, but **applying a clinical threshold rule to longitudinal asymmetry data is itself the kind of interpretation that FDA can read as a medical-device function** (this is precisely what Podimetrics is cleared for). The "75% of ulcers" efficacy claim borrowed from the cleared device makes it worse — quoting a cleared device's clinical outcome to justify our uncleared lookalike invites the "you're doing the same thing without clearance" argument. **Keep the air-gapped logging + a flat "log your foot temps daily and review with your clinician" reminder; drop the asymmetry-threshold rule and the borrowed 75% efficacy stat from the shipping pitch.** This is the single highest regulatory-risk item.

7. **AFib flags / BP zones / "AFib flags = raw device output we log."** The caveat section handles this correctly. One tightening: the **Omron 10-Series AFib indicator is the device's own output** — surfacing it is fine; *acting on it with our own nudge logic* ("you've had 3 AFib flags, call your doctor") is interpretation. Keep our layer to "your device flagged something; review with your clinician."

## (c) Installs that are NOT actually light-lift for an elderly member

8. **Dexcom G7 → xDrip+ → Nightscout** and **Libre 3 → Juggluco → Nightscout.** Both correctly need the paid volunteer, but the G7 path is in the "Better" column implying a step up in ease — it is not; it is sideloaded-APK, firmware-fragile, dev-grade. Honest placement = Premium/dev-grade, same as Libre.

9. **Self-hosted Nightscout on the NAS** is repeatedly treated as a trivial add. Nightscout is a MongoDB + Node service with its own maintenance, auth, and update burden — non-trivial even for the volunteer, and a new attack surface on the vault box. Not light-lift; should carry a "volunteer-maintained service" label.

10. **ESP32-BLE flashing (Omron cuff, Xiaomi scale, CONTEC oximeter, ESP32-S3-BOX).** The plan does flag these as "one-time volunteer flashing," which is honest. Good. But the **Xiaomi Body Comp Scale 2 + ESP32 BLE proxy** is listed at "Better" tier as a routine step — flashing an ESP32 BLE proxy and keeping it paired is fiddly and drift-prone. Keep the air-gapped analog scale as the real recommendation; mark the ESP32 path clearly dev-grade.

11. **HA on Synology Container Manager** at "~200–400MB RAM." On a DS1525+ (your NAS, DSM 7.3.2) this is fine, but HA in Docker on Synology has a well-known **USB-passthrough headache for the Zigbee dongle** (device path changes, container privilege, DSM updates resetting it). Calling the whole spine "plug the USB stick in, HA discovers it" understates this. The Jetson/Mac-mini native path is genuinely easier than the Synology Docker path — say so.

## (d) Cost / spec claims that look off

12. **Sonoff SNZB-04P "5-yr battery."** The SNZB-04P is rated ~**3 years** typical (CR2477, ~1.5–3 yr real-world). Minor, but it's a spec claim; trim to "multi-year."

13. **"HA Connect ZBT-2 $49 … ship both dongles (~$67)."** $17–20 + $49 = $66–69, fine. But note the ZBT-2 *replaces* the need for the ZBDongle-E (it does Zigbee too) — shipping both is only for simultaneous Zigbee+Thread. The "~$67" line is right; just make sure the kit BOM doesn't double-count a coordinator on homes that get the ZBT-2.

14. **"$15 analog scale + manual Nudge log"** and **"$15 analog scale"** vs a **$48 Xiaomi smart scale** — fine, but a true analog (dial) scale gives no digital reading to log automatically; the member reads it and the nudge just reminds. That's honest as written; just don't imply any auto-capture.

15. **Total kit "$95–115/home."** Adding the five: $17–20 + $15–20 + $15–20 + $13.50 + $40–70 = **$100.50–$143.50**. The top of the realistic range is ~$143, not $115. The low end is fine; **the stated upper bound is ~$28 light.** Fix the range to ~$100–145.

16. **CGM "Contour Next One … $20–35."** The meter is often ~$0–20 (frequently free via manufacturer program); strips are the real cost and aren't mentioned. Not wrong for the meter, but the ongoing strip cost is the real spend and should be noted so it's not read as a one-time $20–35.

## (e) Hype not grounded in a real shipping product

17. **The "75% of ulcers" / "same signal the expensive mats use" claim (Play 2).** As above — this is borrowed clinical efficacy from a cleared device applied to an uncleared IR-thermometer-plus-spreadsheet. Real shipping product (Podimetrics/Siren) earned that number through clearance and nurse review; our version has not. Drop or heavily qualify.

18. **Bed-occupancy mat / "under-mattress Zigbee bed-occupancy mat $25–40."** Zigbee under-mattress occupancy mats at that price are mostly **DIY pressure-mat + Zigbee contact-converter** builds, not a clean shipping SKU. Honest, but mark it dev-grade, not a buy-and-stick product.

19. **Everything else (fridge probe, button, door sensor, day-clock, leak pack, dumb oximeter/cuff/scale)** maps to real, currently-shipping, sub-$ SKUs. The core Starter Kit is grounded. Good.

---

## PRIORITIZED FIX LIST

**P0 — regulatory / firewall, fix before it reaches the founder**
1. **Foot-temp (Play 2): strip the asymmetry-threshold rule and the borrowed "75% of ulcers" stat.** Ship "log foot temps daily, review with your clinician" only. This is the one item that drifts into diagnosis *and* hypes a cleared device's number. Highest risk.
2. **Matter-in-Apple/Google-Home device-state leak:** state the rule plainly — safety/PHI-adjacent devices (med-cabinet door, help button) stay HA-only; do not commission them into a vendor ecosystem. If convenience-mirroring is allowed for non-sensitive devices, log it as a known non-PHI device-state egress, don't call it firewall-clean.

**P1 — honesty on effort / placement**
3. **Re-tier the Dexcom G7 → xDrip+ → Nightscout path** from "Better/$0 light-lift" down to dev-grade Premium alongside Libre/Juggluco. Label Nightscout a volunteer-maintained service with its own attack surface.
4. **Add the Synology USB-passthrough caveat** to the spine; stop calling the NAS Docker path "plug in and discover." Recommend the Jetson/Mac-mini native host as the easier default for HA.
5. **Mark ESP32-BLE proxy paths (Xiaomi scale especially) and the bed-occupancy mat as dev-grade**, with the air-gapped dumb device as the real light-lift recommendation.

**P2 — cost / spec corrections**
6. **Fix the kit total to ~$100–145/home** (stated $95–115 upper bound is ~$28 light).
7. **Correct SNZB-04P battery to "multi-year" (not 5-yr).**
8. **Note recurring strip cost** for the Contour Next One so the $20–35 isn't read as total cost of ownership.
9. **Per-SKU Aqara caveat:** confirm each Aqara sensor pairs fully to the generic coordinator (some need the hub for full features); don't blanket-assume hub-free.

**P3 — tightening**
10. Keep our layer strictly "your device flagged X; review with your clinician" for every device that emits its own indicator (Omron AFib, BP zones) — surface the device's output, never compute our own verdict on it.

**What's already right (keep):** the bare-Zigbee-SKU-not-hub rule, the Avoid list (Hero/MedMinder/Podimetrics/Siren/Withings cloud-OAuth/Dexcom-Share/GrandPad/Echo-Nest), the "never install the vendor companion app" checklist item, the offline day-clock as day-one value, the subscription-bricking = member-harm test, and the insulin-fridge play as the marquee. The spine architecture (one dongle → HA on-box → 127.0.0.1 webhook → generic nudge) is sound and genuinely holds the firewall for the Zigbee path.