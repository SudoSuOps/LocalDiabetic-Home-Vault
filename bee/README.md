# Bee — the voice layer (on-box)

Talk to your box. Bee captures speech, transcribes it **on the Jetson**, reads it back to confirm, and
saves it to the NAS vault — a journal entry, a reminder, or a question. **Nothing leaves your home**:
local Whisper, local model (LFM2.5), local Piper voice. Only a generic nudge ever crosses the firewall.

## v1 — push-to-talk (ship-first)
```
hold/press → speak → faster-whisper (Jetson, CUDA) → confirm → POST to the dashboard
   journal  → /api/event (type=journal)   reminder → /api/reminder   ask → /api/ask (doctrine guard)
```

## Install on the Jetson (sigedge)
```bash
# STT: faster-whisper small.en (int8/CUDA) — via jetson-containers or pip
pip install faster-whisper sounddevice soundfile
# TTS: Piper (local ONNX voice)
# download piper + en_US-amy-medium voice (see rhasspy/piper releases)
```

## Run
```bash
# point at the NAS dashboard (the vault)
python3 bee_voice.py --box http://192.168.0.102:8081
# test without a mic (text in, real vault writes out):
python3 bee_voice.py --box http://192.168.0.102:8081 --text "remind me to check my feet at 8am"
python3 bee_voice.py --box http://192.168.0.102:8081 --text "felt good today, walked the dog"
```

## Firewall (non-negotiable)
- STT/TTS/LLM are **all local** — audio + transcripts stay on the box. AVOID cloud STT/TTS/LLM
  (OpenAI/Google/Azure/HA-Cloud) — they ship audio off-box.
- The journal text lives in the vault (`15-voice/` + life events). Only a **generic** nudge crosses to
  the phone (the engine's `scan_phi` backstop refuses any PHI off-box).
- Bee organizes/journals/reminds — **never diagnoses** (ask-Bee routes through `/api/ask`'s doctrine guard).

## Roadmap
- **v2:** "Hey Bee" wake word (openWakeWord, CPU tflite — leaves the GPU free), read-aloud the day, local journal search.
- **v3 — commerce:** voice → on-box shopping list → Instacart `products_link` deep-link cart (member checks out
  themselves; Bee never holds payment/PII). Real API, approval-gated. See `../docs/BEE-VOICE-ROADMAP.md`.
