# Bee — the LocalDiabetic Voice Layer (build roadmap)
*5-hack research · runs-on-Jetson · firewall-safe · 2026-06-20*

I have everything I need from the research. This is a synthesis task, not a code-exploration task — the research already cites the exact files and seams. Producing the build roadmap directly.

# BEE BUILD ROADMAP — The LocalDiabetic Voice Layer
**For DonnyMack · runs-on-Orin · light-lift · firewall-safe · live-vs-framework labeled**

Bottom line: Bee is not a new stack. It is a thin local voice client bolted onto the box that already works — the Jetson runs STT/LLM/TTS, the NAS holds the journal, the Nudge engine already enforces the firewall. The only meaningfully new code is ~3 small dashboard endpoints. Everything voice-related runs 100% on-box: no audio, transcript, or health detail ever crosses. That's structural, not a promise.

---

## 1. THE BEE MVP (ship-first, this quarter)

**Decision: Push-to-talk first. No wake-word in v1.** It's simpler, more reliable, and dodges the GPU-contention + false-trigger risk on a box already running an 8B model. Hands-free is v2.

The smallest real voice loop, all on existing sigedge + NAS:

| Component | Pick (v1) | Why | Status |
|---|---|---|---|
| **Trigger** | Push-to-talk (button / single hardware switch / dashboard tap) | Light-lift, no false fires, no continuous GPU drain | LIVE-capable |
| **VAD** | Silero VAD (built into faster-whisper, ~2MB, <1ms/chunk on CPU) | Ends recording on silence so it "feels live" | LIVE |
| **STT** | **faster-whisper `small.en` int8** (CUDA) | ~250–500MB resident, fits beside LFM2.5; `.en` beats multilingual for English elderly; `small.en` is the accuracy floor for imperfect/elderly speech | LIVE on Jetson (jetson-containers) |
| **LLM** | **LFM2.5-8B-A1B Q4 already on the box** (ollama) | ~4–4.5GB resident; organizes + phrases the read-back; `scan_diagnosis` doctrine guard already wired | LIVE |
| **TTS** | **Piper `en_US-amy-medium`** (warm) or `lessac-medium` (clearest) | ~60MB ONNX, sub-second, pure offline, won't fight the LLM for RAM | LIVE on Jetson |

**RAM note (the one real constraint):** ~7.4GB shared. LFM2.5 is the hog. Run STT and the LLM-organize step **sequentially, not concurrently**. Piper (~60MB) + Silero (~2MB) are free. This fits.

**Data flow:** member holds button → speaks → Silero ends on silence → faster-whisper transcribes on-box → confidence gate + Piper read-back ("I heard: check feet at 8am — right?") → on confirm, POST the transcript to the existing dashboard ingress → it lands in the NAS vault and (for reminders) appends to the Nudge engine. Piper confirms locally. Audio is rendered and discarded; nothing uploaded.

**How it writes the vault + fires the Nudge** (reuses existing code — see §6):
- **Voice journal / life-event** → `POST /api/event` (already exists, `ld_dashboard.py` ~L230) → `log_event()` writes `.state/life_events.jsonl` + mints a receipt (`left_premises:false`). Full transcript stays on box.
- **Voice reminder** → new `/api/reminder` appends to `engine/reminders.json` → the existing cron-driven `ld_remind.py` fires it unchanged. Only the generic nudge string crosses to the phone via ntfy (`scan_phi` backstop already refuses any PHI off-box).
- **Ask-Bee** → route through existing `/api/ask` (~L260) so the `scan_diagnosis` doctrine guard + receipt minting apply — do NOT let voice hit the raw model.

---

## 2. THE PIPELINE DIAGRAM

```
                          ┌─────────────────────── ON THE BOX (sigedge, Jetson Orin) ───────────────────────┐
                          │                                                                                  │
  member ── push-to-talk ─┼─▶ Silero VAD ─▶ faster-whisper small.en (CUDA) ─▶ TRANSCRIPT (PHI, never leaves) │
   (v2: "Hey Bee" wake)   │                                                          │                       │
                          │                          confidence gate + read-back     │                       │
                          │            LFM2.5-8B (ollama, on-box) ◀──── phrase ───────┤                       │
                          │                          │                                │                       │
                          │              Piper TTS ◀──┘ (local audio, discarded)      ▼                       │
                          │                                          ┌──────────────────────────────┐        │
                          │                                          │  route by intent              │        │
                          │                                          │  ├─ journal/life-event        │        │
                          │                                          │  ├─ reminder                  │        │
                          │                                          │  └─ ask-Bee (/api/ask guard)  │        │
                          └──────────────────────────────────────────┼──────────────────────────────┼────────┘
                                                                      │                              │
                          ┌──────── SYNOLOGY NAS = THE VAULT ─────────▼──────────┐                   │
                          │  /api/event → life_events.jsonl + 13-organized-notes │                   │
                          │  /api/reminder → engine/reminders.json               │                   │
                          │  15-voice/ → audio + transcript   14-receipts/ mint  │                   │
                          │  ALL PHI STAYS HERE — NEVER LEAVES                    │                   │
                          └──────────────────────────────┬───────────────────────┘                   │
                                                         │  ld_remind.py (the Nudge)                  │
                                                         │  scan_phi() backstop                       │
              ════════════════════ THE FIREWALL ═════════▼════════════════════════════════════════════
                                    only a GENERIC, non-PHI nudge crosses
                                                         │
                                                         ▼  ntfy → member's phone
                                            "Time to check your feet" (no detail; vault_ref stays on box)
```

PHI crosses NEVER. Models flow down, receipts flow up, generic nudges cross — same invariant the box already enforces.

---

## 3. CAPABILITY TIERS

**v1 — PTT core loop (ship this quarter, ~a day of new code + container wiring)**
- Voice journal: hold, speak, transcript lands in the vault as a `journal` life-event + receipt.
- Voice reminders: "remind me to check my feet at 8" → appends to `reminders.json`, Nudge fires it.
- Ask-Bee: spoken Q&A routed through `/api/ask` (doctrine guard intact). Piper speaks short answers.
- Read-back confirmation on every write (also the low-confidence safety gate).

**v2 — hands-free + accessibility (the elderly/low-vision unlock)**
- "Hey Bee" wake word via **openWakeWord** (custom model, free <1hr Colab train, CPU tflite — leaves GPU free).
- Read-aloud the day: Piper speaks today's reminders/events on request.
- Local journal search: `GET /api/journal?q=` substring v1 → on-box embeddings (nomic-embed via ollama, SQLite+cosine) v2. Never calls the hive.
- Optional: HA Voice Preview Edition ($69 puck) per member — hardware mic-kill switch = literal firewall + trust story.

**v3 — commerce (voice grocery/supply reorder)** — see §4 for the honest split.
- Voice → on-box shopping list in the vault → Instacart deep-link cart → one-tap checkout by the member.
- Supply/Rx reorder as generic nudge + deep-link/care-pack (NOT an API Bee operates).

---

## 4. THE COMMERCE PLAY (honest: real-API vs partner vs human-in-the-loop)

**The key finding (and it's firewall-friendly): real-world voice grocery ordering does NOT need an "order" API, a vendor cloud, or any PHI to cross.** The dominant pattern is a **pre-filled cart deep-link** — Bee builds the list on-box, sends one shoppable URL, the member checks out themselves on the vendor app with their own account + card. Bee never holds payment or PII.

| Path | Reality | Firewall fit |
|---|---|---|
| **Instacart Developer Platform** — `POST /idp/v1/products/products_link` | **REAL API, buildable now.** Send product names+qty → returns a hosted cart URL. Does NOT place orders or take payment. Covers Whole Foods, Kroger, Costco, ALDI, Publix, ~1,500 stores. **Approval-gated (~30–40 days, not self-serve), no public pricing.** | Excellent — only a non-PHI grocery list + a URL cross |
| Kroger Cart API | Real but add-to-cart only, no checkout. **Redundant** with Instacart. Re-verify scopes live. | Same as above, but redundant |
| **Walmart** consumer ordering | **No API.** Portal is B2B-only. Affiliate link-out + commission only. | Link-out only |
| **Amazon Fresh / Whole Foods direct** | **No consumer order API.** PA-API → **Creators API** (PA sunset May 15 2026), affiliate only. Reach Whole Foods *via Instacart*. | Link-out only |
| Delivery leg (DoorDash Drive / Uber Direct) | Real **merchant-side logistics** APIs, contract-gated. This is the *ride-to-doctor / ship-the-shoes* leg — **framework, not a self-serve afternoon.** | Logistics, not shopping |
| **Pharmacy Rx / diabetic supply / shoe reorder** | **No clean consumer API.** Real ones are BAA/PHI-bound (Surescripts/FHIR) → would break the filing-cabinet posture. **Keep it a generic nudge + deep-link + human/partner.** | Must stay deep-link; never auto-submit, never let the "why" cross |

**Firewall stance:** a shopping list is non-PHI (it's food/items), so it *may* cross — but only through an explicit, member-approved, receipted hand-off (the existing `care-pack` pattern), exactly like any export. Ordering is always a **generic off-box action**; the reason/condition stays behind the `vault_ref` on the NAS.

**Cleanest first step (v3.0):** ship the **on-box shopping-list builder first** — LFM2.5 turns "add eggs, low-carb bread, more test strips" + `09-food-cookbooks` into a structured list written to the vault. That's 100% local and trivial. Then push it out as **one generic action**: either an Instacart `products_link` URL via the Nudge ("Your list is ready — tap to check out"), or a one-tap care-pack handoff. Mint a receipt (`phi_touched:false`). **Label Instacart as partner-gated/not-live until access is granted.**

---

## 5. AVOID (firewall violations — name them so nobody reaches for them)

- **Cloud STT:** OpenAI Whisper **API**, Google/Amazon/Azure speech, **HA Cloud / Nabu Casa STT (uses Azure)**. Any of these ships audio off-box. Use the local whisper implementations only. (HA Assist *defaults* can point at HA Cloud — you must explicitly select local engines.)
- **Cloud TTS:** ElevenLabs cloud, Alexa/Google/OpenAI TTS. Use Piper (local ONNX).
- **Cloud LLM:** any hosted model. Use the on-box LFM2.5.
- **Voice satellites that are cloud assistants:** Alexa, Google Assistant. They stream audio to a vendor — forbidden.
- **Continuous streaming STT** on this shared-GPU box — burns GPU 24/7 next to the LLM. Use VAD-bounded batch.
- **XTTS weights** — CPML non-commercial license, unfit for a free-program ship (the idiap *code* is fine; the *weights* aren't). Piper (permissive voices) and Kokoro (Apache/MIT) are clean.
- **Pharmacy refill APIs** (Surescripts/FHIR/PBM) — BAA/PHI-bound; would convert the box from filing-cabinet to covered-entity. Stay deep-link.
- **Giving the LLM raw device/tool control** (HA Ollama "control my home" is experimental, small models err) — route voice through `/api/ask` so the doctrine guard applies.

---

## 6. EXACT NEXT BUILD (the one module first, and what it touches)

**Build first: the voice-journal capture loop — a thin STT daemon that POSTs transcripts to the existing `/api/event`.** This ships the entire core loop while reusing ~90% existing code, and everything else (reminders, ask-Bee, commerce) is a variation on it.

**Concretely:**
1. Stand up **`wyoming-whisper` (faster-whisper `small.en` int8)** from `jetson-containers` on sigedge, push-to-talk + Silero VAD. *(container install, no app code)*
2. Write a small **voice daemon**: capture → transcribe on-box → confidence gate + Piper read-back → on confirm `POST http://<box>:8081/api/event {type:"journal", source:"voice", message:<transcript>}`. *(the only meaningful new glue)*
3. Add a new vault folder **`15-voice/`** for audio + transcript, referenced by `audio_ref`/`transcript_ref` in the event.
4. **Files it touches (all absolute):**
   - `/home/swarm/Desktop/projects/localdiabetic/ld_dashboard.py` — reuse `/api/event` (~L230), `log_event()`+`mint()` (~L115/132), `notify_generic` PHI gate (~L159). Optionally add a ~15-line `/api/journal` writing to `13-organized-notes/`.
   - `/home/swarm/Desktop/projects/localdiabetic/helper/ld_helper.py` — reuse `call_model()` (organize), `scan_diagnosis()` (doctrine guard), `write_note()` (writes `13-organized-notes/`).
   - `/home/swarm/Desktop/projects/localdiabetic/engine/ld_remind.py` — untouched for journal; `scan_phi` already guards the nudge path (used when reminders land in step 2 of the roadmap).
   - `/home/swarm/Desktop/projects/localdiabetic/homeassistant/README.md` — the existing HA→`/api/event` `rest_command` pattern the voice daemon copies.

**Then, in order:** `/api/reminder` → `reminders.json` (voice reminders, Nudge unchanged) · Piper read-back hardening + journal receipt fields (`stt_local:true`) · `GET /api/journal?q=` local search · "Hey Bee" openWakeWord (v2) · on-box shopping-list builder + Instacart deep-link, partner-gated (v3).

**Honest status labels:** STT/TTS/wake-word/LLM/`/api/event`/Nudge are all **LIVE-capable today** (real, shipping, CUDA-ready on Orin). The new daemon + `/api/reminder` + `/api/journal` are **~a day of build, not a project.** Hands-free wake-word is **v2 (designed, not yet on the box)**. Instacart grocery + supply/Rx reorder are **framework/partner-gated — not live until access is granted.** Ride/shoe-shipping logistics remain framework, consistent with the mission.


---

# Appendix — Research


## Stt Whisper

I have everything needed for a complete, grounded answer. Here is the research report.

---

# Bee Voice Layer — Local STT on the Jetson Orin Nano (sigedge)

**Bottom line up front:** Ship **faster-whisper `small.en` (int8) for the journal/transcripts + `whisper_trt base.en` for fast command turns**, gated by **silero-vad** and woken by **openWakeWord** with a custom "Hey Bee" model. Glue it together with the **Wyoming protocol** (already containerized for Jetson by NVIDIA's own `jetson-containers`). Everything runs 100% on-box, CUDA-accelerated — no audio ever leaves sigedge, so it is firewall-clean by construction. This is **buildable now**, not framework or roadmap.

---

## 1. The three STT engines, head-to-head on Orin Nano

NVIDIA's own `whisper_trt` repo publishes real Orin Nano benchmarks (20s audio clip):

| Engine | tiny.en time | base.en time | Memory (base.en) | Verdict for Bee |
|---|---|---|---|---|
| openai-whisper (PyTorch) | 1.74s | 2.55s | 666 MB | Baseline, slowest — skip |
| **faster-whisper** (CTranslate2) | 0.85s | n/a in their table | 404 MB (tiny) | **Best general pick** — int8, VAD built-in, distil-compatible |
| **whisper_trt** (TensorRT) | **0.64s** | **0.86s** | **439 MB** | **Fastest + lowest memory** — best for short command turns |

All three transcribe 20s of audio in **under 1 second** on Orin Nano → all are **comfortably real-time** at tiny/base. The question is accuracy vs. latency tradeoff, not "can it keep up."

**whisper.cpp** — Real and CUDA-capable (`cmake -B build -DGGML_CUDA=1`), has a genuine streaming example (`whisper-stream`, samples every 0.5s), and supports quantized models (Q5_0). But: it does **not** advertise Jetson support, is **not** in the `jetson-containers` speech suite, and on Jetson the CUDA build is a fiddly compile vs. a pre-built container. **Use it only if you want a single self-contained C++ binary with no Python.** For Bee's NAS/Python ecosystem, faster-whisper is the lower-friction path.

**Recommendation:** faster-whisper as the default engine; keep `whisper_trt` as the low-latency option for wake-word-triggered command turns where 0.86s round-trip matters.

---

## 2. Model size: tiny vs base vs small (and Orin Nano headroom)

Whisper model footprints (from openai/whisper):

| Model | Params | VRAM | Relative speed | English-only variant |
|---|---|---|---|---|
| tiny | 39M | ~1 GB | ~10x | `tiny.en` |
| base | 74M | ~1 GB | ~7x | `base.en` |
| small | 244M | ~2 GB | ~4x | `small.en` |
| medium | 769M | ~5 GB | ~2x | `medium.en` |

Critical for an **English-speaking elderly** user base: **use the `.en` variants.** OpenAI explicitly notes "the `.en` models tend to perform better, especially for `tiny.en` and `base.en`." There is no accuracy reason to carry the multilingual model for this population, and `.en` is faster.

**Sizing call for sigedge (~7.4GB RAM, also running ollama LFM2.5-8B):** The 8B LLM is the RAM hog. STT must stay lean. `small.en` at int8 is ~250–500MB resident — fits alongside the LLM. **Do not go above `small.en`**; `medium` (~5GB) would contend with the LLM.

**Accuracy vs. size:** Real-world WER drops meaningfully from tiny→base→small, then flattens base→small→medium. **`base.en` is the floor for acceptable journaling; `small.en` is the sweet spot** — noticeably better on hard audio (the elderly case below) while still real-time on Orin.

---

## 3. Elderly speech — the honest accuracy caveat

This is the weakest spot and you should plan for it explicitly. Whisper was trained on broad web audio and does well on clear adult speech, but **accuracy degrades on the things common in elderly speakers**: slower/dysarthric speech, breathiness, tremor, dentures affecting sibilants, low volume, and regional accents. No off-the-shelf local model fully solves this. Mitigations that actually help:

- **Go up a model size** for this population — `small.en` over `base.en` buys real WER margin on imperfect audio. This is the single biggest lever.
- **Good mic + Speex noise suppression** (openWakeWord ships Speex NS support) matters more than model choice for soft/distant voices.
- **Keep it command/journal-shaped, not open dictation.** Bee organizes/reminds/journals — short, bounded utterances transcribe far better than free-form paragraphs.
- **Never auto-act on a low-confidence transcript.** faster-whisper returns segment/word confidence — gate any action (a reminder, a logged life-event) behind a confirmation read-back ("I heard: take meds at 6 — is that right?"). This is also doctrine-safe: Bee confirms, never assumes.

Honest flag: budget for a tuning pass with **real recordings of your actual members** once you have consent, and measure WER per-user. There is no published "elderly Whisper WER on Orin" number to lean on — you'll establish your own.

---

## 4. distil-whisper — useful, with a catch

- **What it is:** knowledge-distilled Whisper, **English-only**, **~6x faster** than large-v3 and **within ~1% WER** of it. Sizes: `distil-small.en` (166M), `distil-medium.en` (394M), `distil-large-v3` (756M).
- **faster-whisper compatibility: YES** — SYSTRAN confirms distil checkpoints run in faster-whisper; `distil-large-v3` was co-designed for it. So you get distil's speed *inside* the CTranslate2/int8 runtime you're already using.
- **The catch for Orin:** even `distil-medium.en` (394M) is bigger than `small.en` (244M). On a RAM-constrained box already running an 8B LLM, distil's win (near-large accuracy at medium-ish cost) only pays off if you can spare the memory. **For sigedge, plain `small.en` int8 is the pragmatic pick; revisit `distil-small.en`/`distil-medium.en` only if you offload the LLM or move STT to a dedicated process window.** Not the day-one choice, but a clean upgrade path.

---

## 5. Streaming vs. batch

- **Batch (record-then-transcribe):** simplest, most accurate, lowest engineering cost. Wake word → record until silence (VAD) → transcribe the clip → act. **This is the right v1 for Bee** — journaling and commands are naturally utterance-shaped, and a <1s transcribe on Orin makes the wait imperceptible.
- **Streaming (continuous):** whisper.cpp `whisper-stream` and faster-whisper streaming exist, but streaming Whisper is hacky (it re-runs overlapping windows) and burns GPU continuously — bad for a 24/7 always-on box sharing the GPU with the LLM. **Skip streaming for v1.** VAD-bounded batch gives you "feels live" without the cost.

---

## 6. VAD — Silero (use it, it's free real-time)

**Silero VAD** is the clear pick and is **already integrated into faster-whisper** (enabled by default for batched transcription):
- ~**2MB** model, **<1ms per 30ms chunk on a single CPU thread** — essentially free, doesn't touch the GPU.
- Trained on 6000+ languages, robust to noise; 8kHz + 16kHz; ONNX (4–5x faster path available); `pip install silero-vad`.
- Real-time by design (IoT/edge/voicebot use cases).

VAD is what makes the batch flow feel live: it ends recording on silence, so Bee responds the instant the user stops talking. **No reason to use anything else.**

---

## 7. Wake word — openWakeWord + a custom "Hey Bee"

**openWakeWord** (dscripka) is the right call and is **Jetson-containerized** (`wyoming-openwakeword`):
- Pre-trained models for common phrases; runs **CPU tflite** — tiny overhead, leaves the GPU for STT/LLM.
- **Custom wake words are first-class:** there's a Google Colab notebook that trains a new word in **<1 hour, free**. So **"Hey Bee" is a real, buildable custom model**, not a stretch. (The Jetson container even ships a sample custom `jetson` wake word as a worked example.)
- Speex noise suppression supported (helps for soft elderly voices in a room).
- One caveat on the Jetson container: it currently runs the **CPU `.tflite`** path; the CUDA `.onnx` path is marked WIP. That's fine — wake word on CPU is the norm and frees the GPU.

Alternatives (microWakeWord, Picovoice Porcupine) exist; **Porcupine is proprietary/licensed and cloud-tied for some features → firewall/cost risk. openWakeWord is fully local and open — stick with it.**

---

## 8. How it all plugs into THE BOX (build ON it)

NVIDIA's `jetson-containers` ships a complete **Wyoming** voice suite (the Home Assistant voice protocol) pre-built for L4T/JetPack R36 — i.e. directly compatible with sigedge:
- `wyoming-openwakeword` — "Hey Bee" detection
- `wyoming-whisper` — STT (wraps **faster-whisper**)
- `wyoming-piper` — local **TTS** (Bee's voice out — also fully on-box, firewall-clean)
- `wyoming-assist-microphone` — mic capture/orchestration

These are network-protocol services (ports 10400/10300/etc.) you can wire together without adopting full Home Assistant. **Recommended architecture:**

```
Mic → openWakeWord ("Hey Bee", CPU)
     → assist-microphone + Silero VAD (records until silence)
     → faster-whisper small.en int8 (CUDA)  →  transcript stays on-box
     → [your logic] confidence gate + read-back
        ├─ writes VOICE JOURNAL / life-event → NAS vault via existing /api/event (ld_dashboard.py)
        ├─ schedules/acks reminders → existing ld_remind.py ("the Nudge")
        └─ Piper TTS speaks the confirmation back, locally
```

**Firewall fit — clean by construction:** audio, VAD, transcription, and TTS all execute on sigedge. The transcript is PHI and **never leaves the box** — it goes straight into the NAS vault via the existing `/api/event` endpoint, exactly like typed life-events do today. Only the **generic, non-PHI nudge** that `ld_remind.py` already emits crosses to the phone via ntfy. **No vendor cloud STT (no Whisper API, Alexa, Google) is involved — so no firewall violation.** This is the whole reason to do local STT, and this stack delivers it.

**Doctrine fit:** Bee transcribes and organizes; the confidence-gated read-back means it confirms before logging — it still never diagnoses or doses. The LFM2.5-8B already on-box can phrase the read-back/confirmation, keeping that on-box too.

---

## 9. Install effort & what to ship

| Component | Effort | Notes |
|---|---|---|
| faster-whisper (STT) | **Low** | Pre-built `dustynv/faster-whisper:r36.4.0` container (5.3GB), or pip + CTranslate2. CUDA int8 ready. |
| Silero VAD | **Trivial** | Built into faster-whisper; or `pip install silero-vad`. |
| openWakeWord + "Hey Bee" | **Low–Medium** | Container exists; custom word = free <1hr Colab train, then drop the `.tflite` in. |
| Wyoming glue | **Low** | NVIDIA containers + docker-compose provided. |
| Piper TTS (bonus, voice out) | **Low** | Same suite, fully local. |
| whisper_trt (optional fast path) | **Medium** | First run builds a TensorRT engine (one-time); 0.64–0.86s turns. |

**Lightest reliable local STT to ship:** **faster-whisper `small.en` int8 + Silero VAD + openWakeWord "Hey Bee," wired over Wyoming.** Runs real-time on Orin, fits in RAM beside the LLM, is firewall-clean, and drops straight into the existing NAS-vault + nudge-engine plumbing. Add `whisper_trt base.en` later if command-turn latency needs shaving, and `distil-small.en` later if you want more accuracy headroom and can spare the memory.

**Honest flags:**
- Elderly-speech WER is the real risk; mitigate with `small.en` (not tiny/base), a good mic + Speex NS, bounded utterances, and a confirmation read-back. Plan a per-user tuning/measurement pass — there's no published Orin-elderly WER to rely on.
- The Jetson openWakeWord container runs CPU tflite (CUDA path WIP) — fine, and actually preferable for GPU contention.
- Don't run continuous streaming on this shared-GPU box; VAD-bounded batch is the correct v1.
- distil-whisper is English-only and only pays off if RAM allows — upgrade path, not day-one.

**Sources:**
- [NVIDIA-AI-IOT/whisper_trt (Orin Nano benchmarks)](https://github.com/NVIDIA-AI-IOT/whisper_trt)
- [dusty-nv/jetson-containers — speech & smart-home/wyoming packages](https://github.com/dusty-nv/jetson-containers/tree/master/packages/speech)
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [huggingface/distil-whisper](https://github.com/huggingface/distil-whisper)
- [snakers4/silero-vad](https://github.com/snakers4/silero-vad)
- [dscripka/openWakeWord](https://github.com/dscripka/openWakeWord)
- [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)
- [openai/whisper (model sizes)](https://github.com/openai/whisper)

(Note: the `WebSearch` tool was down during this session; all findings above are pulled directly from primary repos/benchmark tables via fetch and `gh`, which is actually stronger sourcing than search snippets.)


## Tts Voice

I have everything I need. The box, the firewall seam (`ld_remind.scan_phi` / `notify_generic`), the on-box receipt pattern, and the current state of each TTS engine on Jetson are all confirmed.

---

# Bee Voice Layer — Local TTS on the Jetson Orin (sigedge)

**Bottom line:** Ship **Piper TTS** as the Bee voice. It is the only engine that is (a) already containerized for Jetson Orin by NVIDIA, (b) real-time on the Orin even on CPU, (c) fully offline by construction, and (d) drop-in to the existing nudge/event seam. Keep **Kokoro (via kokoro-onnx)** as the "premium warmth" upgrade once Piper is in members' homes. Treat **Coqui/XTTS, Parler, Chatterbox** as roadmap, not v1 — they're heavier, slower, and (XTTS) license-tainted. Everything below runs behind the firewall; no audio, text, or transcript ever leaves the box.

## The verdict table

| Engine | Runs local on Orin? | Real-time? | Install effort | Firewall fit | Warmth for elderly/low-vision | v1 call |
|---|---|---|---|---|---|---|
| **Piper** | ✅ Yes — official `piper1-tts` in jetson-containers; also `pip install piper-tts`, pure ONNX, runs on CPU | ✅ Strong — ~1.6s of audio per 1s compute on medium models on a *Pi 4*; the Orin is far faster, well sub-second per sentence | **Lowest** — pip + one .onnx + .onnx.json voice file | ✅ Perfect — ONNX, no network, no account | Good. `lessac`/`amy` medium are clear and calm; not the warmest but very intelligible | **SHIP THIS** |
| **Kokoro-82M** (via `kokoro-onnx`) | ✅ Yes — `kokoro-tts` in jetson-containers; kokoro-onnx runs CPU+GPU, ~80MB int8 / ~300MB fp | ⚠️ Near-real-time (claimed on M1; on Orin expect ~RTF≤1 on GPU, slower on CPU) | Medium — onnx runtime + model + espeak-ng | ✅ Clean — MIT runtime / Apache-2.0 model, offline | **Best warmth** — `af_heart` voice is notably warm/natural; the standout for a comforting Bee | **PHASE 2 upgrade** |
| **Coqui / XTTS** (idiap fork, the maintained one) | ✅ Runs, PyTorch | ⚠️ XTTS streams <200ms latency but is heavy (LLM-class); GPU-hungry on Orin's ~7.4GB shared RAM alongside LFM2.5 | High — PyTorch 2.2+, large models | ✅ Offline, but ⚠️ **XTTS weights are CPML non-commercial** — license risk for a 501c3-adjacent ship | Excellent + voice cloning, but overkill | **Roadmap / avoid XTTS weights** |
| **Parler-TTS Mini** | ⚠️ Technically yes | ❌ **0.9B params, not optimized for edge** — model card itself says server-side, not real-time edge | High | ✅ Apache-2.0, offline | Good prompt-controlled voice, but too slow | **No for v1** |
| Cloud (Alexa/Google/OpenAI/ElevenLabs) | — | — | — | ❌ **FIREWALL VIOLATION** — streams audio off-box | — | **DECLINE** |

## Why Piper wins for the Bee specifically

1. **Already on the box's platform.** NVIDIA's `jetson-containers` ships `piper1-tts` (plus `whisper`/`faster-whisper`/`whisper_trt` for the STT side later). This is the same JetPack/ARM64 path sigedge already runs LFM2.5 on. No porting, no surprises.
2. **Tiny RAM footprint.** Piper medium voices are 15–20M params / ~60MB. That coexists comfortably with LFM2.5-8B on the Orin's ~7.4GB — Kokoro (300MB) and especially XTTS/Parler (GB-class PyTorch) compete with the LLM for memory. For a box that already hosts the on-box model, Piper's frugality matters.
3. **Real-time with margin.** Home Assistant's own docs benchmark Piper medium at 1.6s audio/sec on a *Raspberry Pi 4*. The Orin Nano is several times that — Bee will speak a reminder with no perceptible lag, even CPU-only, leaving the GPU for LFM2.5.
4. **Offline by construction.** Pure ONNX inference against a local file. There is no cloud mode to accidentally enable — the firewall is satisfied structurally, exactly the property the project demands.
5. **This is the Home Assistant local-voice stack.** The IoT strategy doc already plans HA on the box with the **HA Voice Preview Edition ($59) running local Whisper/Piper**. Choosing Piper means the Bee voice and the future hands-free voice-control path are *the same engine* — Wyoming protocol, fully local, no second stack to maintain.

## Voice selection (warm/clear for elderly/low-vision)

Piper's en_US voices come in tiers — `medium` = 22.05kHz (the sweet spot), `high` = 22.05kHz/28–32M params (best quality, still small). Recommended audition order, all on the Orin:
- **`en_US-lessac-medium`** — the cleanest, most neutral-clear narrator; the safe default for intelligibility.
- **`en_US-amy-medium`** — warmer female tone; strong candidate for the "slightly-warm Bee."
- **`en_US-hfc_female-medium` / `en_US-ryan-high`** — alternates to A/B for warmth vs clarity.
- **Pick by listening** at `rhasspy.github.io/piper-samples` on the actual NAS speaker, with a real elderly member — perceived warmth is device- and listener-dependent.

If members want more warmth than Piper's best, that is the trigger to add **Kokoro `af_heart`** as a per-member upgrade — same ONNX-offline discipline, just a bigger model.

## How it plugs into THE BOX (build-now, not reinvent)

The seam already exists in `ld_dashboard.py` and `ld_remind.py`. Voice is a **new local output channel**, governed by the same PHI rule:

- **`notify_generic()`** (ld_dashboard.py:159) and the nudge engine already gate every off-box message through **`ld_remind.scan_phi()`**. A Bee voice channel sits at the *same chokepoint*: the text Bee speaks is the **declared generic nudge string**, never a vault record. Detail stays behind the `vault_ref` pointer the member opens on the box.
- **Crucial firewall distinction:** TTS audio is a **LOCAL-ONLY** channel (speaker on/near the box), so unlike the webhook/email off-box channels it can speak the on-box title/pointer if desired — but the safe default is to speak only the generic nudge, identical to what crosses the wire. Audio is rendered and played **on sigedge and discarded**; nothing is uploaded.
- **Concrete v1 wiring:** add a `voice` channel to `ld_remind.py` alongside the existing local-log rail. On a due reminder, call Piper locally → write a temp WAV → play to the box speaker → delete. Mint the existing per-fire receipt (the `mint()`/`log_event()` pattern at ld_dashboard.py:115/132 already does this) noting `phi_touched: false`, `channel: voice-local`. **Fail-open**: a TTS error must never block the always-works local log or the ntfy push — wrap it exactly like the existing isolated channels.
- **STT (the hands-free other half) is Phase 2:** `faster-whisper`/`whisper_trt` from jetson-containers, also fully local. Same firewall: a transcript is PHI and **never leaves the box** — only a parsed generic intent ("log foot check done") feeds the existing `/api/event` endpoint (ld_dashboard.py:230).

## Honest flags

- **Buildable now:** Piper TTS reminder voice on sigedge → real, low-effort, this-sprint. The seam (`scan_phi` gate + receipt mint + fail-open channels) is already live.
- **Framework, not yet built:** the hands-free STT loop, wake-word, and HA Voice PE satellite integration are designed in the IoT doc but not yet shipped on the box — don't claim them as live.
- **License watch:** **XTTS weights are CPML (non-commercial)** — keep them out of a shippable free-program build even though the idiap Coqui *code* is MPL-2.0. Piper (GPL-3.0 engine, permissive voice models) and Kokoro (Apache-2.0 model / MIT runtime) are clean.
- **Memory contention:** the Orin Nano's ~7.4GB is shared CPU/GPU. Piper is the only TTS here that won't fight LFM2.5 for RAM; if you move to Kokoro/XTTS, plan to run TTS on CPU or time-share with the LLM.
- **Piper maintainership:** the Open Home Foundation is actively seeking maintainers for `piper1-gpl` (v1.4.2, Apr 2026) — healthy and current, but worth tracking; the ONNX voice files are stable regardless of repo activity.

**Recommended path:** Phase 1 = Piper `lessac`/`amy` medium as a local voice channel in `ld_remind.py`, gated by the existing PHI seam, with per-fire receipts. Phase 2 = Kokoro `af_heart` warmth upgrade + `faster-whisper` hands-free intent capture, both via jetson-containers, both on-box.

Sources:
- [OHF-Voice/piper1-gpl (Piper TTS engine)](https://github.com/OHF-Voice/piper1-gpl)
- [Piper VOICES.md (quality tiers / sample rates)](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md)
- [Piper voice samples](https://rhasspy.github.io/piper-samples/)
- [Home Assistant local voice assistant (Wyoming + Piper + Whisper, fully local)](https://www.home-assistant.io/voice_control/voice_remote_local_assistant/)
- [hexgrad/kokoro (Kokoro-82M)](https://github.com/hexgrad/kokoro)
- [thewh1teagle/kokoro-onnx (offline ONNX runtime, CPU+GPU)](https://github.com/thewh1teagle/kokoro-onnx)
- [idiap/coqui-ai-TTS (maintained Coqui/XTTS fork)](https://github.com/idiap/coqui-ai-TTS)
- [parler-tts/parler-tts-mini-v1 (Parler-TTS Mini)](https://huggingface.co/parler-tts/parler-tts-mini-v1)
- [NVIDIA jetson-containers /packages/speech (piper1-tts, kokoro-tts, xtts, whisper, faster-whisper, whisper_trt)](https://github.com/dusty-nv/jetson-containers/tree/master/packages/speech)


## Assistant Loop

I have enough. The model name on the box (`LFM2.5-8B-A1B-GGUF:Q4_K_M`) tells me it's an 8B MoE with ~1B active, Q4 — that's the key RAM fact I need (already noted in the dashboard). I have a complete, verified picture. Let me compose the research report.

The MoE detail matters for the RAM concurrency analysis: an 8B-A1B (A1B = ~1B active params) at Q4 is roughly 4-4.5GB resident — that's why it fits the 7.4GB Jetson and why adding STT/TTS is feasible. Let me write the final report.

---

# Bee Voice Layer — Local Pipeline Research

## Bottom line up front

**Don't build a custom wake-word→STT→LLM→TTS orchestrator. Build voice as a thin client on top of what's already on the box.** The cleanest local pipeline is: a **Wyoming/ESPHome voice satellite → Home Assistant Assist pipeline → your existing dashboard's `/api/event` and `/api/ask`**. You already have HA wired into the box (`homeassistant/README.md` posts to `/api/event` with a generic-nudge firewall). Voice is just three more local services (wake word, STT, TTS) plugged into the same HA you've already adopted, plus two custom HA intents that call your existing endpoints. Everything runs on-box. Nothing streams to a vendor cloud.

The single biggest finding: **`wyoming-satellite` is deprecated, replaced by [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant)** (Open Home Foundation), which **explicitly supports `linux/aarch64`, names Jetson as a target, runs on a generic Linux box, and connects to HA over the ESPHome API**. That is the Jetson satellite. It does local wake word (openWakeWord/microWakeWord) on-device.

---

## The three build options, scored on your criteria

### Option A — Custom from scratch (wake → STT → LLM → TTS, your own glue)
- **Runs on Jetson?** Yes. **Real-time?** Yes if you use the right STT. **Install effort:** HIGH — you reimplement VAD, wake-word gating, streaming STT, barge-in, TTS playback, audio device handling, timers/announcements. **Firewall fit:** Perfect (you control everything). **Plug-in:** You'd write the `/api/event` + `/api/ask` calls anyway.
- **Verdict:** Only worth it if HA proves too heavy. You'd be rebuilding `wyoming-satellite`/Linux Voice Assistant by hand. Not recommended as the starting point.

### Option B — Home Assistant Assist + Wyoming/ESPHome satellite ← RECOMMENDED
- **Runs on Jetson?** Yes — HA in Container Manager/Docker on the box (already your documented pattern), STT/TTS as local Wyoming containers, Linux Voice Assistant as the satellite on the Jetson (or the $69 [Voice Preview Edition](https://www.home-assistant.io/voice-pe/) as a plug-and-play hardware mic puck).
- **Real-time?** Yes (numbers below). **Install effort:** MEDIUM — mostly compose files + two custom intents. **Firewall fit:** Excellent — Assist "can run fully on your own hardware"; choose local Whisper + local Piper + local conversation agent and nothing leaves. **Plug-in:** Cleanest of all — you already have the HA→`/api/event` bridge built.
- **Verdict:** This is the cleanest path. It reuses your existing HA investment, gives you wake-word/timers/announcements/multi-language/accessibility for free, and the elderly/low-vision angle is exactly HA Assist's design target. The Voice PE has a **physical mute switch that cuts mic power** — a literal hardware firewall, great for the elderly-trust story.

### Option C — Rhasspy 3
- **Runs on Jetson?** Yes. **Real-time?** Yes. **Install effort:** MEDIUM-HIGH. **Firewall fit:** Excellent (fully offline by design). **Plug-in:** Workable but you'd build the dashboard integration yourself.
- **Verdict:** Rhasspy 3 is by the **same author** (Michael Hansen / now Open Home Foundation) and was effectively **folded into the HA Assist + Wyoming stack** — the Wyoming protocol *is* the Rhasspy-3 inter-service protocol (HA's own docs link to `rhasspy3/docs/wyoming.md`). Standalone Rhasspy 3 gives you HA-independence but loses the prebuilt satellite, intent UI, and the bridge you already wrote. Pick this only if you want voice with **zero** Home Assistant dependency. Otherwise B strictly dominates it.

**Recommendation: Option B.** You already chose Home Assistant for sensors (`homeassistant/README.md`, `docs/IOT-DEVICE-STRATEGY.md`). Voice is the same HA, three more local add-ons, two custom intents. Don't fork the stack.

---

## The components (all local, all current as of 2026)

| Stage | Pick | Why | Jetson reality |
|---|---|---|---|
| **Wake word** | **openWakeWord** (or microWakeWord on the satellite) | Runs on-device, "ok_nabu" / "hey_jarvis" prebuilt; custom wake word ("hey Bee") trainable | Tiny CPU cost, runs on the satellite before any audio streams |
| **STT** | **WhisperTRT** (`NVIDIA-AI-IOT/whisper_trt`) for the Jetson, exposed via Wyoming | TensorRT-optimized for Orin | **base.en: 0.86s for a 20s clip; tiny.en: 0.64s. Memory only ~439MB.** ~3× faster than vanilla Whisper. Real-time with headroom. |
| | fallback: `faster-whisper` via `wyoming-faster-whisper`, or `whisper.cpp` (CUDA, `-DGGML_CUDA=1`, `whisper-stream`) | Standard HA path | base/tiny models, CUDA-accelerated |
| **LLM / conversation agent** | **Your existing ollama LFM2.5-8B-A1B Q4** via HA's [Ollama integration](https://www.home-assistant.io/integrations/ollama/) | Already running on `/api/generate` | A1B = ~1B active params; Q4 ≈ 4–4.5GB resident — fits alongside ~0.5GB STT/TTS in the 7.4GB budget |
| **TTS** | **Piper** — now **`OHF-Voice/piper1-gpl`** (old `rhasspy/piper` archived Oct 2025; latest **v1.4.2, Apr 2026**) via `wyoming-piper` | Fast local neural TTS, `pip install piper-tts`, low/medium/high voice tiers, many languages | Runs fine CPU-only on ARM; pick a "medium" voice for warm, clear elderly-friendly speech |

**RAM caution (the one real constraint):** the Jetson is ~7.4GB and LFM2.5 already lives there. WhisperTRT (~0.45GB) + Piper (~0.2GB) + openWakeWord fit, but don't also try to run HA *core* on the Jetson — **run HA on the NAS (Synology Container Manager, your documented pattern) and keep the Jetson as the compute/satellite.** STT/TTS containers can live on the NAS too and call back; or keep STT on the Jetson for the GPU win. Test the concurrent footprint under load before committing.

---

## How it wires into your two use-cases (this is the load-bearing part)

Both journal and reminders become **HA custom intents** (or sentence triggers) that call the endpoints you already built. No new servers.

### Voice JOURNAL (speak → transcribe → save to NAS vault)
1. "Hey Bee, journal: *my foot looked red this morning*" → satellite wake → WhisperTRT STT → text.
2. HA custom intent `LDJournal` fires a `rest_command` POST to the **dashboard's `/api/event`** (already exists, line ~230 of `ld_dashboard.py`) — OR, better, add a tiny new `/api/journal` endpoint that writes the **full transcript** into the vault (`13-organized-notes/` is where the helper already writes, via `write_note()` in `helper/ld_helper.py`).
3. The transcript is PHI → **it stays on the box, in the vault, mints a receipt** (`mint()` already exists, `left_premises:false`). Piper replies "Saved to your journal." — that confirmation is generic, no PHI spoken back over any network (it's local audio anyway).
4. **Firewall:** transcription happens on-box (WhisperTRT), text is written on-box, nothing crosses. This is fully compliant with your HARD-INVARIANT.

*Small new code:* a `/api/journal` POST handler in `ld_dashboard.py` (~15 lines, mirrors `/api/event`) writing to `13-organized-notes/` and minting a receipt. That's the only meaningful build.

### Voice REMINDERS (speak → create a reminder in the Nudge engine)
1. "Hey Bee, remind me to check my feet every morning at 8" → STT → HA intent `LDReminder` extracts the schedule.
2. Two clean options:
   - **(a)** HA intent → LLM (LFM2.5) parses natural language into the `reminders.json` schema your engine already defines (`daily@08:00`, `weekly@MON,THU@09:00`, `once@2026-06-26@18:00`). POST to a new tiny `/api/reminder` endpoint that appends to `engine/reminders.json`. The existing cron-driven `ld_remind.py` then fires it — **the entire Nudge engine is reused unchanged.**
   - **(b)** Simpler/safer: HA's own templated sentences map to fixed reminder slots (no LLM parse), append to `reminders.json`. More robust for the elderly than free-form NLU.
3. **Firewall holds automatically:** the reminder's `nudge` text is the only thing that ever leaves the box (per the engine's existing PHI backstop, `scan_phi`), and reminders default to generic nudges. The *spoken* detail and `vault_ref` stay local. You don't have to add new firewall logic — the Nudge engine already enforces it.

*Small new code:* a `/api/reminder` POST that validates + appends to `reminders.json`. ~20 lines.

### The on-box assistant loop ("ask Bee a question")
You **already have `/api/ask`** (line ~260, calls `ld_helper.call_model` → ollama LFM2.5, with `scan_diagnosis` guarding against doctrine violations). Wire HA's conversation agent to either (a) the Ollama integration directly, or (b) a `rest_command` to `/api/ask` so you keep your **diagnosis-marker firewall and receipt-minting**. **Prefer (b)** — it routes voice through the same doctrine guard (`scan_diagnosis`, the "never diagnoses or doses" rule) you already wrote, instead of letting HA talk to the raw model.

---

## Honest flags

- **Cloud-only / firewall violations to avoid:** Alexa, Google Assistant, OpenAI Whisper *API*, ElevenLabs cloud TTS, HA Cloud (Nabu Casa) STT (it uses Azure). All stream audio off-box → forbidden. Use the **local** Whisper/Piper path only. (HA Assist *defaults* can point at HA Cloud — you must explicitly select local engines.)
- **Buildable now vs. framework:** STT (WhisperTRT), TTS (Piper), wake word (openWakeWord), HA Assist, the Ollama agent, and your `/api/event`+`/api/ask`+Nudge engine are **all real and shipping today**. The only **new code** is ~3 small dashboard endpoints (`/api/journal`, `/api/reminder`, optional intent glue) + the HA intent YAML. That's a day of work, not a project.
- **Roadmap/experimental labels (real):** **Linux Voice Assistant** (the Jetson satellite) is labeled **experimental** — works, prebuilt Docker image, ~500 GitHub stars, active dev, but not yet "stable." **HA's Ollama "control my home" tools** are also marked **experimental** and **small models make mistakes** — which is *why* you should route voice through your `/api/ask` doctrine guard rather than giving the LLM raw device/tool control. **piper1-gpl** is "seeking maintainers" (healthy but worth noting).
- **Latency expectation:** wake (instant) + STT (~0.6–0.9s WhisperTRT) + LFM2.5 generate (the variable part — a MoE 1B-active Q4 is fast, but watch tokens for long answers) + Piper (sub-second). For journal/reminder (short utterances, short confirmations) this is comfortably real-time. For open Q&A, cap `num_predict` (you already set 768) and keep answers short.
- **Accessibility win is real:** Voice PE has a hardware mic-kill switch and on-device wake word — exactly the trust + low-vision story for elderly members. A $69 puck per member is a cleaner deploy than asking them to wire a mic to the Jetson.

## Files that matter (all absolute)
- `/home/swarm/Desktop/projects/localdiabetic/ld_dashboard.py` — `/api/event` (≈L230), `/api/ask` (≈L260), `notify_generic` PHI firewall (≈L159), `mint()` receipts (≈L115). **Add `/api/journal` + `/api/reminder` here.**
- `/home/swarm/Desktop/projects/localdiabetic/helper/ld_helper.py` — `call_model()` (L61, ollama `/api/generate`), `scan_diagnosis()` (L83, doctrine guard), `write_note()` (L88, writes to `13-organized-notes/`). **Journal writes reuse this.**
- `/home/swarm/Desktop/projects/localdiabetic/engine/ld_remind.py` + `engine/reminders.json` — the Nudge engine + schema. **Voice reminders append here; engine unchanged.** PHI backstop (`scan_phi`) already enforces the firewall on off-box nudges.
- `/home/swarm/Desktop/projects/localdiabetic/homeassistant/README.md` — the existing HA→`/api/event` bridge + `rest_command` pattern. **The voice intents copy this exact pattern.**

## Sources
- [Home Assistant Voice Control](https://www.home-assistant.io/voice_control/)
- [Wyoming protocol (rhasspy/wyoming)](https://github.com/rhasspy/wyoming)
- [HA Wyoming integration](https://www.home-assistant.io/integrations/wyoming/)
- [HA local Assist pipeline guide](https://www.home-assistant.io/voice_control/voice_remote_local_assistant/)
- [HA Ollama conversation agent](https://www.home-assistant.io/integrations/ollama/)
- [wyoming-satellite (deprecated)](https://github.com/rhasspy/wyoming-satellite) → [Linux Voice Assistant (replacement, aarch64/Jetson)](https://github.com/OHF-Voice/linux-voice-assistant)
- [Home Assistant Voice Preview Edition](https://www.home-assistant.io/voice-pe/)
- [jetson-containers speech packages](https://github.com/dusty-nv/jetson-containers/tree/master/packages/speech)
- [whisper.cpp (CUDA + streaming)](https://github.com/ggml-org/whisper.cpp)
- [WhisperTRT (Jetson Orin benchmarks)](https://github.com/NVIDIA-AI-IOT/whisper_trt)
- [Piper TTS — now OHF-Voice/piper1-gpl (v1.4.2, Apr 2026)](https://github.com/OHF-Voice/piper1-gpl)


## Voice Journal

I have enough to deliver an honest, grounded research report. Synthesizing now.

---

# Bee Voice Layer — Research Report

Voice journaling for the diabetic's daily life, built ON the box that already exists. Bottom line: a fully-local STT → vault-journal → optional on-box organize pipeline is **buildable now** on sigedge with mature, CUDA-accelerated open software. It slots cleanly into the existing `ld_dashboard.py` / receipt / nudge architecture without reinventing anything. The "commerce" hook is the only piece that is **partner-gated, not self-serve**.

## 1. What's already on the box (verified — build on this, don't reinvent)

I read the live code. The voice layer must reuse these exact patterns:

- **On-box model:** `helper/ld_helper.py` → `call_model(host, model, prompt)` hits `ollama /api/generate` with LFM2.5-8B, has `SYSTEM` = "organizer, NEVER diagnose," `strip_reasoning()` for `<think>` blocks, and `scan_diagnosis()` backstop (DIAGNOSIS_MARKERS list). **The summary step already exists — voice just feeds it text.**
- **Life-event timeline:** `ld_dashboard.py` → `log_event(etype, title, message, ...)` appends to `.state/life_events.jsonl` AND mints a receipt. `EVENT_TYPES` is a fixed set (`fridge, help, meds, foot, glucose, note, mood, milestone, appointment, supply, ...`). **A voice journal entry is just a new event type, e.g. `journal`/`voice`.**
- **Receipt minter:** `mint(kind, payload)` stamps `left_premises:false, called_hive:false` on every receipt in `14-receipts/`. `ld_helper.write_note()` adds `diagnosis_given:false, diagnosis_backstop_flags:[], escalation_present:true` and writes the organized note to `13-organized-notes/`.
- **Firewall guard:** `ld_remind.py` → `scan_phi(text)` (PHI_HINTS list) + `notify_generic()` which **refuses to push any string that scans as PHI** off-box. ntfy is the generic-nudge channel.
- **Ingress already exists:** `POST /api/event` (with optional `X-LD-Token`) is the documented local ingress — Home Assistant already posts to it (`homeassistant/README.md`). **A voice daemon posts to the same endpoint.** The `homeassistant/` dir + Wyoming protocol is the natural home for a voice satellite.

Key files: `/home/swarm/Desktop/projects/localdiabetic/helper/ld_helper.py`, `/home/swarm/Desktop/projects/localdiabetic/ld_dashboard.py` (lines 115–176, 230–276), `/home/swarm/Desktop/projects/localdiabetic/engine/ld_remind.py` (scan_phi ~186), `/home/swarm/Desktop/projects/localdiabetic/homeassistant/README.md`.

## 2. Local STT — the capture engine (all run on Jetson Orin Nano, CUDA, no cloud)

Evaluated for: runs-on-Orin / real-time / install effort / firewall fit. **All of these are 100% local — zero firewall violation.** Whisper *API* (OpenAI cloud) would be a violation; these are the on-device implementations.

| Option | Runs on Orin? | Speed (Orin Nano) | Install | Verdict |
|---|---|---|---|---|
| **whisper_trt** (NVIDIA-AI-IOT) | Yes, TensorRT | tiny.en **0.64s** / base.en **0.86s** per clip; ~440–490 MB; **~3x faster than vanilla Whisper**; built-in live mic + VAD | Medium — `jetson-containers` has a prebuilt `whisper_trt` container | **TOP PICK for Jetson.** Purpose-built for this exact board, smallest memory, live transcription included. |
| **faster-whisper** | Yes (CTranslate2/CUDA) | Fast, well-supported; container in jetson-containers | Easy | Strong fallback; great accuracy, big language coverage, easy Python API. |
| **whisper.cpp** | Yes (`-DGGML_CUDA=1`, cuBLAS) | `tiny.en`/`base.en` real-time; has `stream` example (samples every 0.5s) | Medium (compile) | Most portable, stdlib-friendly, Q5 quantized models. Good if you want a single C++ binary, no Python. |
| **Moonshine** (Useful Sensors, MIT) | Yes (runs down to RPi/MCU) | **Streaming: 73–107ms latency, WER 6.65–7.84%**, *beats* Whisper-large-v3 at 6x fewer params | Easy (`pip`) | **Best for true real-time/interactive** "talk and watch it appear." Newer, English-focused. Worth a head-to-head vs whisper_trt. |

**Recommendation:** journaling is **batch, not conversational** — the member taps/holds, speaks a paragraph, releases. That favors **whisper_trt base.en** (best accuracy-per-watt on *this* board, ~0.9s, native to jetson-containers). Keep **Moonshine** in the lab for the future hands-free "always listening" mode. RAM budget fits: whisper_trt base.en ≈ 440 MB, leaving headroom alongside LFM2.5 in the ~7.4 GB (note: run STT and the 8B summary **sequentially**, not concurrently, to stay within RAM).

## 3. Wake word + TTS (the hands-free / low-vision accessibility unlock)

- **openWakeWord** (`pip install openwakeword`, fully offline, MIT) — trainable custom "**Hey Bee**" wake word via their Colab synthetic-speech pipeline. Runs fine on RPi3-class CPU; comfortable on Orin. Caveat: *not* for bare microcontrollers (they point those to `microWakeWord`) — irrelevant here, the Jetson is plenty.
- **Piper** (now `OHF-Voice/piper1-gpl`; old `rhasspy/piper` archived Oct 2025) — fast local neural TTS, fully offline, runs on RPi/Jetson, many voices. This is how Bee **speaks back** ("Got it — saved to your journal") — critical for **low-vision/elderly** members. Confirmation-only by doctrine: Bee reads back the entry and generic nudges, never reads PHI aloud to anyone but the member at the box.

## 4. The integration path — Wyoming + Home Assistant (lowest-lift, reuses existing dir)

The project already runs Home Assistant on the box and already posts to `/api/event`. The cleanest build is the **Wyoming voice satellite** stack, all in `jetson-containers`:

```
mic → wyoming-openwakeword ("Hey Bee") → wyoming-whisper (whisper_trt/faster-whisper, on Jetson)
    → transcript (TEXT, stays on box)
    → POST http://<box>:8081/api/event  {type:"journal", message:<transcript>, source:"voice"}
        → log_event() → .state/life_events.jsonl + mint() receipt   [PHI stays on NAS]
    → (optional) ld_helper.call_model() organize → 13-organized-notes/  + diagnosis backstop
    → wyoming-piper TTS read-back: "Saved to your journal."   [generic confirmation only]
```

This is **buildable now** — every box in that chain is verified-real and CUDA-capable on Orin, and the right-hand half already exists in the repo. The only new code is a thin voice daemon (or HA `assist` pipeline + automation) that POSTs the transcript to `/api/event`.

## 5. Data model — the voice journal as a defendable, member-owned record

Extend the existing JSONL event, don't invent a new store. Proposed schema (mirrors `log_event`):

```json
{ "type": "journal", "source": "voice", "at": "2026-06-20T19:02:11",
  "title": "Morning note", "message": "<full transcript — STAYS ON BOX>",
  "audio_ref": "15-voice/2026-06-20T190211.wav",   // raw audio on NAS, never crosses
  "transcript_ref": "15-voice/2026-06-20T190211.txt",
  "stt_model": "whisper_trt-base.en", "stt_seconds": 0.9,
  "summary_ref": "13-organized-notes/journal-20260620.md",  // optional LFM2.5 organize
  "severity": "info" }
```

Plus a per-capture **receipt** in `14-receipts/` (reuse `mint`): `left_premises:false, called_hive:false, on_box:true, diagnosis_given:false, diagnosis_backstop_flags:[], stt_local:true`. **That receipt — hash-chainable into the same ledger as the rest of the house — is what makes the journal *defendable* and provably member-owned: a verifiable record that the audio and text never left the box.** Suggest a new vault folder `15-voice/` (audio + transcripts) alongside `13-organized-notes/`.

## 6. Search-your-own-journal, locally (no cloud index)

- **v1 (ship now, stdlib):** the transcript text is already in `life_events.jsonl` + `15-voice/*.txt`. Grep/substring search over local text — add a `GET /api/journal?q=` to the dashboard. Zero new deps, fully local, instant.
- **v2 (semantic, still local):** local embeddings via **ollama** (`nomic-embed-text` / `all-minilm`) on the *same* sigedge box → store vectors in a `.state/journal.index` (SQLite + numpy cosine, stdlib-adjacent) → "when did I last write about my foot?" Never calls the hive; embeddings computed on-box from on-box text. This honors the firewall identically to the summary path.

## 7. Doctrine / firewall compliance (honest flags)

- **GREEN — fully local & buildable now:** whisper_trt / faster-whisper / whisper.cpp / Moonshine STT, Piper TTS, openWakeWord, the journal store, on-box LFM2.5 organize, local search. None stream audio off-box. The organize step already has the `scan_diagnosis` backstop and "confirm with your clinician" escalation baked in (`ld_helper.py`).
- **RED — firewall violations to AVOID (name them so nobody reaches for them):** OpenAI Whisper *API*, Google/Amazon/Azure speech services, Alexa/Google Assistant satellites, ElevenLabs cloud TTS. Any of these = audio/transcript leaves the box = invariant broken. Use the local equivalents above.
- **Doctrine guard for summaries:** journaling raises a new risk — a member may *speak* symptoms ("my foot hurts, sugar was 240"). The summary prompt must stay strictly "organize/reflect-back, NEVER interpret." Reuse `SYSTEM` + `DIAGNOSIS_MARKERS`; consider adding journal-specific markers. The generic-nudge path is already protected by `scan_phi()` refusing PHI off-box — so even a "you have a journal note" phone nudge can't leak content.

## 8. The commerce / errands integration — honest assessment

The brief's "helps with errands" + a separate "commerce one." Researched the realistic hook (groceries/diabetic-friendly food, which ties to `09-food-cookbooks`):

- **Instacart Developer Platform API** *(docs.instacart.com/developer_platform_api)* — has **Create Recipe Page** and **Create Shopping List Page** endpoints that return an instacart.com link from a list of ingredients. This is the cleanest fit: Bee builds a shopping list **on-box** from a meal plan, then hands off a *generic* product link — **no PHI crosses, just grocery items.** **CAVEAT (honest):** access/approval requirements and cost are **not self-serve-documented** — the docs route you to "contact Instacart" / enterprise service desk. So this is **framework, not live**: needs a partner application, not a `pip install`. The older **Instacart Connect API** is explicitly **enterprise/partner-only** ("contact your Instacart representative") — not usable by an individual dev.
- **Firewall fit:** commerce is inherently an off-box action, so it must follow the existing `care-pack` pattern (`/api/carepack` writes the request locally + mints a receipt, "we'll reach out"). A grocery list is non-PHI by nature (it's food items), so it *can* cross — but it should still go through an explicit, receipted, member-approved hand-off, exactly like the HARD-INVARIANT requires for any export.
- **Verdict:** buildable as a **framework now** (list-builder on-box is trivial and 100% local; the Instacart link is a partner-gated add-on). Recommend shipping the **on-box list-builder first** (LFM2.5 turns `09-food-cookbooks` + a spoken "add eggs and low-carb bread" into a list in the vault), and treat the Instacart link as a Phase-2 partner integration — **flag it as not-yet-live until the developer-platform access is actually granted.**

## Recommended build order

1. **Whisper satellite** — `jetson-containers` `wyoming-whisper` (whisper_trt base.en) + a daemon that POSTs transcripts to the existing `/api/event` as `type:"journal"`. New `15-voice/` vault folder. *(Ships the core loop reusing 90% existing code.)*
2. **Receipts + read-back** — extend `mint`/`log_event` for the journal receipt; add Piper TTS confirmation. *(Makes it defendable + accessible.)*
3. **Local search** — `GET /api/journal?q=` substring v1, then on-box embeddings v2.
4. **"Hey Bee" wake word** — openWakeWord custom model for hands-free, low-vision mode.
5. **Errands (framework)** — on-box voice→shopping-list in the vault; Instacart Developer Platform link as a *flagged, partner-gated* Phase-2.

Sources: github.com/dusty-nv/jetson-containers, github.com/NVIDIA-AI-IOT/whisper_trt, github.com/ggml-org/whisper.cpp, github.com/usefulsensors/moonshine, github.com/OHF-Voice/piper1-gpl (ex rhasspy/piper), github.com/dscripka/openWakeWord, docs.instacart.com/developer_platform_api. (Live web *search* was down during this session; findings came from direct repo/doc fetches, which succeeded.)


## Commerce

Kroger's portal won't load in this environment. I have firm, primary-source-confirmed findings on the highest-value items and reliable knowledge of the rest. I'll synthesize the report now rather than burn more time on a portal that times out.

---

# Bee Voice-Commerce Research: Real APIs, Privacy Fit, Buildable-Now vs Framework

## The single most important finding (and it's good news for the firewall)

**Voice grocery ordering does NOT require any vendor cloud, any PHI to cross, or any "place an order" API. The dominant real-world pattern is a pre-filled cart deep-link, where the member completes checkout themselves on the vendor's own app with their own account and payment.** This is a clean, generic, non-PHI action that fits the firewall perfectly. Bee builds the list on the box, sends a single shoppable URL out, and the human taps "checkout." Nobody gets the member's health context, and Bee never holds payment or PII.

---

## Vendor-by-vendor: what's actually real (June 2026)

### 1. Instacart Developer Platform — BUILDABLE NOW (the anchor) ✅
**Primary-source confirmed** ([docs.instacart.com](https://docs.instacart.com/developer_platform_api/)).
- **What it is:** `POST /idp/v1/products/products_link` ("Create Shopping List Page" / "Create Recipe Page"). You send **line items by product name (preferred — Instacart name-matches) or UPC**, plus quantities, brand filters, and health filters (organic, gluten-free, etc.). It returns a **`products_link_url`** — an Instacart-hosted page.
- **The checkout flow (critical):** "When users click the link, they can select a store, add products to their cart, and check out." **The API does NOT place an order and does NOT process payment.** It is **deep-link cart creation only.** The member checks out on Instacart with their own account/card.
- **Covers:** Instacart's whole retailer network — which includes **Whole Foods, Kroger, Costco, Wegmans, ALDI, Publix, and ~1,500 retailers**. This one integration is your widest reach.
- **Access:** **Approval-gated, not self-serve.** Apply at instacart.com/company/business/developers; docs cite **~30–40 days** to production. No public pricing/rev-share/rate-limit numbers (negotiated/NDA).
- **Firewall fit: excellent.** Only product names + quantities cross — a shopping list is non-PHI. No audio, no transcript, no journal. The member is the one who authenticates and pays.
- **Verdict:** This is the one to build on. It is the most realistic "order groceries by voice" path that exists today, and it's structurally privacy-clean.

### 2. Walmart — NO consumer ordering API (B2B only) ❌→partner
**Primary-source confirmed** ([developer.walmart.com](https://developer.walmart.com/)). The developer portal is **entirely B2B**: Marketplace (sellers), 1P Suppliers, Transportation Carriers (Walmart GoLocal), and Walmart Connect Ads. **There is no public consumer cart/checkout/grocery-ordering API.**
- The only consumer-facing programmatic surface is the **Walmart affiliate program (via Impact / the old Walmart.io affiliate API)** — that gives **product feeds + tracked deep links**, i.e. you can generate a link to a Walmart product and earn commission, but **you cannot build a cart or place an order.** Affiliate = link-out + commission, not errand automation.
- **Verdict:** Not buildable as a voice-errand action. At best, an affiliate link-out. Real Walmart grocery ordering = partnership/BD, not an API.

### 3. Amazon Fresh / Whole Foods — NO ordering API; affiliate is mid-migration ❌→partner
- There is **no public Amazon API to place a Fresh or Whole Foods order** on a consumer's behalf. (Whole Foods is reachable as an *Instacart* retailer — see #1 — which is the practical path.)
- **Product Advertising API 5.0** (the Associates/affiliate API) is **being deprecated May 15, 2026** and replaced by the new **Creators API** ([webservices.amazon.com](https://webservices.amazon.com/paapi5/documentation/)). Even PA-API never placed orders — its old `AddToCart` was removed years ago; it returns product data + affiliate links and requires an **Amazon Associates account with qualifying sales** to keep access.
- **Verdict:** Whole Foods ordering → go through Instacart. Direct Amazon = affiliate link-out only, and you'd build against the **Creators API**, not PA-API, given the 2026 sunset.

### 4. Kroger Developer Portal — Cart "add-to-cart" only, no checkout ⚠️ buildable-but-limited
(Knowledge-based; Kroger's portal timed out repeatedly in this environment — flag for live re-verification.)
- Kroger publishes real public APIs: **Products, Locations, Identity/Profile, and Cart.**
- The **Cart API does an `PUT` "add items to cart"** for an OAuth-authenticated Kroger customer (authorization_code flow, a write scope). **It does not expose checkout/order placement** — the member still completes the order in Kroger's own app.
- Public app access historically caps at modest rate limits and Kroger has periodically tightened/gated the Cart scope.
- **Verdict:** Functionally similar privacy story to Instacart (you populate a cart, the human checks out), but **redundant** with Instacart (which already covers Kroger banners). Only worth a direct integration if you want Kroger-native loyalty/pricing. **Re-verify scopes live before committing.**

### 5. The delivery leg (DoorDash Drive / Uber Direct) — real, but it's logistics, not shopping ⚠️ partnership
- **DoorDash Drive** and **Uber Direct** are real "delivery-as-a-service" APIs: you (the merchant/partner) create a delivery and their courier picks up and drops off. **They move goods; they don't shop a grocery list for a consumer.** These are merchant-side, contract/onboarding-gated, and priced per-delivery.
- **Relevance to Bee:** This is the API layer behind the *ride/shoe-shipping/"ride to the doctor"* framework in the mission — the **logistics leg**, not the grocery-ordering leg. Buildable as a **partnership/framework**, honestly not a self-serve afternoon.

### 6. Pharmacy / supply reorder — NO open consumer API; this is partner/human territory 🚩
- **CVS, Walgreens, and major PBMs do not offer a public third-party "refill my prescription" API.** Refill-by-app is locked to their own apps; programmatic access exists only via **B2B/health-system integrations under BAAs (FHIR/NCPDP via Surescripts, etc.)** — which would pull you into **covered-entity / PHI territory and break the filing-cabinet posture.**
- **Diabetic supplies (test strips, CGM sensors, lancets) and diabetic-shoe reorder:** no clean consumer API either; these run through **DME suppliers / insurance** — partnership + human-in-the-loop.
- **Firewall-safe pattern that IS buildable now:** treat a reorder as a **generic nudge + pre-staged action**, reusing your existing `ld_remind.py`. Bee says (generically, off-box): *"time to reorder your supplies"* / *"refill is due"* — the **detail stays behind the `vault_ref` pointer on the NAS**, exactly like the Nudge already does for PHI. The actual refill is a one-tap **deep-link to the pharmacy's own app**, or a logged human/partner task. **Never** auto-submit an Rx and never let the reason (the condition) cross.
- **Verdict:** Reminder + deep-link + human/partner = buildable now and firewall-clean. A true "API reorder" = partnership/roadmap, and the PHI sensitivity means you probably *want* it to stay a deep-link, not an API you operate.

---

## How this plugs into THE BOX (build ON what's running)

The voice→commerce pipeline is fully local except the final shoppable link, and it reuses everything you already have:

1. **Local STT on the Jetson** — capture the spoken list on `sigedge`. Use `whisper.cpp` or `faster-whisper` (small/base int8) on the Orin Nano; both run real-time on Orin-class CUDA and keep audio **on the box**. **No Alexa/Google/Whisper-API** — that would be the firewall violation called out in the brief. Audio + transcript never leave.
2. **Intent + list parsing** — your **on-box LFM2.5-8B in ollama** turns "add eggs, low-sugar bread, and more test strips" into a structured `{name, qty}` list. No cloud LLM.
3. **List lives in the NAS vault** — write the list as a **life event via the existing `/api/event` on `ld_dashboard.py`**; it's a journal-class artifact and stays in the vault.
4. **The ONE generic thing that crosses** — call Instacart `products_link` with just product **names + quantities** (non-PHI), get back the `products_link_url`.
5. **Push the link out via the existing Nudge** — send the shoppable URL through **`ld_remind.py` + ntfy** to the member's phone as a generic action ("Your grocery list is ready — tap to check out"). The member taps and checks out on Instacart. **Mint a per-fire receipt** (you already do this) recording that a generic order-link action crossed, `phi_touched:false`.
6. **Pharmacy/supply** = same Nudge mechanism, deep-link instead of API, `vault_ref` keeps the "why" on the box.

This means **only product names + a URL ever cross the firewall** — and the member, not Bee, authenticates and pays. That keeps the filing-cabinet (HIPAA) and organization-only (FDA) posture intact: Bee organizes a list and reminds; it never diagnoses, doses, or holds payment.

---

## Honest buildable-now vs framework-vs-roadmap

| Capability | Status | Notes |
|---|---|---|
| **Groceries/food by voice (Whole Foods, Kroger, Costco, ALDI, Publix, +1,500 stores)** | **Buildable now** | Via **Instacart Developer Platform** deep-link cart. ~30–40 day approval. Member checks out themselves. **Start here.** |
| Local voice capture + list parsing on the box | **Buildable now** | whisper.cpp/faster-whisper + LFM2.5 already on `sigedge`; reuse NAS `/api/event` + ntfy. |
| Kroger-native cart | Buildable, redundant | Add-to-cart only, no checkout. Re-verify scopes live. Instacart already covers Kroger. |
| Walmart / Amazon grocery ordering | **Not via API** | Walmart portal = B2B only; Amazon = no consumer order API. **Affiliate link-out only** (Amazon Creators API post-May-2026). |
| Delivery / ride leg (DoorDash Drive, Uber Direct) | **Framework / partnership** | Real APIs, merchant-side, contract-gated. This is the "ride to the doctor / ship the shoes" logistics leg — matches it being framework-not-live in the mission. |
| Pharmacy Rx refill by API | **Roadmap / partnership** | No clean consumer API; real ones are BAA/PHI-bound (would break filing-cabinet posture). Do it as **generic nudge + deep-link + human/partner**. |
| Diabetic supply / shoe reorder | **Framework / partnership** | DME + insurance; no consumer API. Nudge + human/partner now. |

**Bottom line:** Ship **Instacart deep-link cart driven by local voice on the Jetson + the existing NAS/Nudge plumbing** — that is a genuinely buildable, firewall-clean "order groceries by voice" feature for elderly/low-vision members, with only a product list and a URL ever crossing. Walmart/Amazon direct ordering and pharmacy/supply reorder are honestly **partnership/framework**, not APIs you can self-serve — and for pharmacy you likely *want* it to stay a deep-link to keep PHI on the box.

**Verification caveat:** WebSearch was intermittently unavailable and Kroger's developer portal timed out repeatedly in this run. Instacart (the anchor), Walmart's B2B-only portal, and Amazon's PA-API→Creators-API deprecation are **primary-source confirmed**; the Kroger Cart-API specifics and DoorDash Drive details are knowledge-based and flagged for a live re-check before you commit engineering to them.

Sources: [Instacart Developer Platform docs](https://docs.instacart.com/developer_platform_api/), [Instacart products_link / shopping list endpoint](https://docs.instacart.com/developer_platform_api/api/products/create_shopping_list_page), [Walmart Developer Portal](https://developer.walmart.com/), [Amazon Product Advertising API 5.0 docs (deprecation notice)](https://webservices.amazon.com/paapi5/documentation/).



---

# Red-Team

I have the ground truth I need. Two important findings: (1) the roadmap's claimed `EVENT_TYPES`/`log_event` does **not** include a `"journal"` type — it maps unknown types to `"note"`; (2) the memory ground-truth says the box is the **Synology DS1525+ NAS running DSM 7.3.2 / Python 3.8**, while the roadmap repeatedly asserts the Jetson Orin Nano runs the whole STT/LLM/TTS stack. Let me confirm the memory's deployment claim.

The memory is explicit: "LIVE ON SYNOLOGY NAS (192.168.0.102, DS1525+/DSM7.3.2/py3.8): engine on cron... + self-hosted ntfy server." And sigedge (the Jetson @192.168.0.79) is the OpenDiabetic *compute grinder*, which runs LFM2.5. So the LLM does live on the Jetson. The roadmap's hardware claim is plausible. But I should be realistic about whether an 8B + Whisper-small + Piper all fit on an Orin Nano. Let me write the review.

This is a synthesis/judgment task and I now have all the ground truth. Producing the skeptic review.

---

SKEPTIC REVIEW — Bee Voice Plan — gate before founder

Ground-truth checks I ran against the live code (not the roadmap's word):
- `ld_dashboard.py` `/api/event` + `log_event()` + `mint()` + `notify_generic()` exist as described (L230, L132, L115, L159). `mint()` stamps `left_premises:false`, `called_hive:false`. Confirmed real seam.
- `notify_generic()` does gate on `ld_remind.scan_phi()` before any off-box push. Confirmed real backstop.
- `ld_helper.call_model()`, `scan_diagnosis()`, `write_note()` exist and the `/api/ask` route does run the doctrine guard. Confirmed.
- HA `rest_command` → `/api/event` pattern the daemon is told to copy exists in `homeassistant/README.md`. Confirmed.

The firewall architecture of the plan is sound — STT/LLM/TTS all named as local engines, audio discarded, only generic nudges cross. That part is honest. The problems are in the details below.

(a) CLOUD-service-presented-as-local — firewall risk
- None of the v1 voice picks are cloud. faster-whisper, Piper, Silero, LFM2.5, openWakeWord are all genuinely local. The AVOID list (§5) correctly names the cloud traps (Whisper API, Nabu Casa/Azure STT, ElevenLabs, Alexa/Google satellites). This section is actually a strength — keep it.
- ONE soft hole: §6 step 2 has the daemon `POST`ing the transcript over plain `http://<box>:8081`. That's on-LAN so not a firewall *violation*, but the transcript is PHI in clear text on the wire. The existing `LD_EVENT_TOKEN` header is described as "optional." For a PHI payload it must be mandatory, and ideally loopback-only (127.0.0.1) since STT and dashboard are the same box. Flag as a hardening requirement, not a violation.

(b) Won't run real-time on a Jetson Orin Nano — REALISM PROBLEM (highest-severity technical flag)
- The roadmap's own "~7.4GB shared" line is the tell. The base Orin Nano is 8GB; the Super is 8GB too (only the AGX Orin has 32–64GB). After DSM/JetPack + the OS + ollama runtime overhead, you do not have a clean 7.4GB. LFM2.5-8B-A1B Q4 at ~4–4.5GB + faster-whisper small.en int8 (~0.5GB loaded, but with CUDA context + cuBLAS/cuDNN workspace it's more like 1–1.5GB resident) + Piper + Silero + the HTTP servers is a tight-to-over-budget fit on 8GB. The roadmap half-admits this with "run STT and LLM sequentially, not concurrently" — but sequential execution directly contradicts the "feels live" claim. Cold-loading/unloading an 8B between every turn on an Orin Nano is multi-second, not real-time.
- Also unstated: which Jetson. Memory ground-truth has sigedge = a Jetson at 192.168.0.79 running LFM2.5 as a *dedicated grinder*. If Bee shares that exact box, voice STT now contends with the OpenDiabetic worker loop (the autonomous 24/7 grinder) for the same GPU — a contention the roadmap never addresses. If it's a *separate* Orin Nano per member, the 8GB budget problem above bites hard.
- small.en on an Orin Nano is ~1–3s for a short utterance with VAD — acceptable for PTT. The unrealistic part is the *combined resident footprint + the 8B being live*, not whisper alone. The honest framing is "PTT with a perceptible pause," not "feels live."

(c) Commerce claims overstating real API vs partnership/human step
- §4 is mostly honest and self-aware (it explicitly splits real-API / link-out / framework, and labels Instacart "approval-gated ~30–40 days, not self-serve"). Good. But three overstatements remain:
  - "Instacart Developer Platform — REAL API, buildable now." Contradicts its own "approval-gated, not self-serve, no public pricing" line three columns over. "Buildable now" should read "applied-for now; buildable only after partner approval." For a brand whose spine is "never vaporware," do not let "buildable now" stand next to an unapproved partner gate.
  - The whole §3 v3 tier is presented in the same table cadence as the LIVE v1 — a reader skims it as roadmap-equivalent. The honest-status paragraph at the very end does label it framework/partner-gated, but the *table* doesn't carry that label inline. Put the LIVE / FRAMEWORK / PARTNER-GATED tag in every row, not just the closing note.
  - Pharmacy/Rx/diabetic-supply/shoe reorder: §4 handles this correctly (no clean consumer API, BAA-bound, keep it deep-link + human). This is the one most likely to be misread by a founder as "Bee reorders your supplies." Keep the "generic nudge + human/partner, never auto-submit" framing loud.

(d) Drift toward diagnosis
- The plan routes Ask-Bee through `/api/ask` so `scan_diagnosis()` applies — correct and verified. Good instinct.
- The residual drift risk is the read-back/confirmation loop. Piper speaking the LLM's phrasing back ("I heard: check feet at 8am") is fine for a *reminder*, but if a member voice-journals symptoms ("my foot is red and weeping"), the LLM-organize step phrasing that back, spoken aloud, can cross from organize into implied interpretation. The `scan_diagnosis` backstop only catches a fixed marker list (`"you have "`, `"the cause is"`, etc.) — it won't catch soft interpretive phrasing. Recommend: voice-journal capture should write the *raw transcript verbatim* to the vault and NOT run it through the LLM-organize/read-back at all. Read-back the transcript literally, not a model rephrase. Reserve the LLM for explicit Ask-Bee.

(e) Install effort that isn't light-lift
- "~a day of new code" is plausible for the daemon glue. The understated lift is the *container/runtime* side on a Jetson: jetson-containers wyoming-whisper, getting CUDA faster-whisper to load alongside ollama's CUDA context, Piper ONNX runtime, and the mic hardware/ALSA capture on the box. For a founder shipping to "Mary, 75, who has no clue how to set it up" (MODEL.md), none of this is light-lift *at the member's house*. It's light-lift for the builder on sigedge; it is NOT a shippable-to-Mary appliance yet. The roadmap should not let "light-lift" read as "Mary plugs it in." The HA Voice Preview puck ($69, v2) is the actual path to member-light-lift and it's correctly parked in v2.
- Also: a new `15-voice/` vault folder is fine, but adding a `"journal"` event type is NOT free — see the verified bug below.

VERIFIED CODE BUG the roadmap glosses
- §1 says voice journal lands "as a `journal` life-event." But `EVENT_TYPES` in `ld_dashboard.py` (L128) is `{fridge, help, meds, foot, glucose, safety, device, note, mood, milestone, appointment, supply}` — there is no `journal`. `log_event()` (L134) silently coerces any unknown type to `"note"`. So the plan as written produces `type:"note"`, not `type:"journal"`, and the "route by intent → journal" diagram is fiction until `EVENT_TYPES` is amended. Small fix, but it's exactly the kind of "presented as existing when it doesn't" that the brand can't ship.

PRIORITIZED FIX LIST
1. (b, blocking) Pin the hardware and prove the budget before any "feels live" claim. State which Jetson and how much RAM. If it's an 8GB Orin Nano, drop "feels live," commit to PTT-with-a-pause, and benchmark the real resident footprint of LFM2.5-Q4 + faster-whisper-CUDA + Piper concurrently before promising it fits. If Bee shares sigedge with the OpenDiabetic grinder, resolve GPU contention explicitly.
2. (d, blocking for honesty) Voice-journal writes the raw transcript verbatim to the vault; do NOT run journal capture through the LLM-organize/read-back. Reserve LLM + read-back for explicit Ask-Bee only. Keeps the organize/diagnose line bright.
3. (verified bug) Add `"journal"` (and `"voice"` if used) to `EVENT_TYPES` in `ld_dashboard.py` L128, or stop claiming the event lands as `journal`. Don't ship a diagram that the code coerces away.
4. (a, hardening) Make `LD_EVENT_TOKEN` mandatory for the voice daemon path and bind the STT→dashboard POST to 127.0.0.1 (same box). PHI transcript must not ride the LAN in clear text with an "optional" token.
5. (c) Re-label §4: change "REAL API, buildable now" → "partner-gated; buildable only post-approval." Add inline LIVE / FRAMEWORK / PARTNER-GATED tags to every commerce row and every §3 tier row, not just the closing paragraph.
6. (e) Replace "light-lift" with two honest tiers: "light-lift for the builder on sigedge" vs "NOT yet a plug-in appliance for the member." Point member-light-lift at the v2 HA Voice puck, and say so.
7. (c, keep) Preserve the pharmacy/Rx/supply "generic nudge + human/partner, never auto-submit, the why never crosses" framing — it's the most-likely-to-be-misread line and the plan currently gets it right.

Files cited: `/home/swarm/Desktop/projects/localdiabetic/ld_dashboard.py` (EVENT_TYPES L128, log_event L132, mint L115, notify_generic L159, /api/event L230, /api/ask L260), `/home/swarm/Desktop/projects/localdiabetic/helper/ld_helper.py` (call_model L61, scan_diagnosis L83, write_note L88, DIAGNOSIS_MARKERS L52), `/home/swarm/Desktop/projects/localdiabetic/engine/ld_remind.py` (scan_phi L186, post_webhook L192), `/home/swarm/Desktop/projects/localdiabetic/homeassistant/README.md` (rest_command pattern, firewall notes §3).

Net: firewall design is sound and the AVOID list is a real asset. The honesty gaps are the Orin Nano "feels live" performance claim, the "Instacart buildable now" vs partner-gate contradiction, the "light-lift" conflation of builder-effort with member-effort, and one factual code mismatch (`journal` type doesn't exist). Fix 1–4 before it reaches the founder.