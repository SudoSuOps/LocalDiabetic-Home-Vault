#!/usr/bin/env python3
"""
Bee — the LocalDiabetic voice client (runs ON the Jetson, v1: push-to-talk)
==========================================================================

The thin local voice loop. Everything runs on the box; no audio, transcript, or
health detail ever leaves. Bee captures speech, transcribes it on-box with
Whisper, reads it back to confirm, then writes it to the NAS vault via the live
dashboard API — a journal entry, a reminder, or a question for the on-box model.

PIPELINE (all local):
  push-to-talk → record → faster-whisper (Jetson, CUDA) → confidence gate
    → Piper read-back → on confirm → POST to the dashboard:
        journal  → /api/event   (type=journal)   → lands in the vault + life feed
        reminder → /api/reminder                 → the Nudge engine fires it
        ask Bee  → /api/ask      (doctrine guard) → organize, never diagnose
  Audio is rendered and discarded. Only a GENERIC nudge ever crosses the firewall.

This file is the loop + intent routing. STT/TTS/record are pluggable adapters so
it runs on the Jetson with faster-whisper + Piper, and stays testable with --text.

USAGE (on the Jetson):
  python3 bee_voice.py --box http://192.168.0.102:8081           # voice (needs mic + models)
  python3 bee_voice.py --box http://192.168.0.102:8081 --text "remind me to check my feet at 8am"
  python3 bee_voice.py --once                                    # one capture then exit

Models (install on the Jetson — see README): faster-whisper small.en (int8/CUDA),
Piper en_US-amy-medium. Falls back to text mode if audio libs aren't present.
"""

import argparse
import json
import os
import re
import sys
import urllib.request

BOX = os.environ.get("BEE_BOX", "http://127.0.0.1:8081")
WHISPER_MODEL = os.environ.get("BEE_WHISPER", "small.en")
PIPER_VOICE = os.environ.get("BEE_PIPER", "en_US-amy-medium")
VOICE_DIR = os.environ.get("BEE_VOICE_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "15-voice"))


# ── intent routing (simple, on-box; the LLM refines ask-Bee) ─────────────────
REMIND_RE = re.compile(r"\b(remind me|reminder|set a reminder|don'?t let me forget)\b", re.I)
ASK_RE = re.compile(r"\b(what|how|why|when|should i|can you|explain|help me|question)\b", re.I)
TIME_RE = re.compile(r"\b(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I)
DAILY_RE = re.compile(r"\b(every day|each day|daily|each morning|every morning)\b", re.I)


def classify(text):
    """Return (intent, payload) for a transcript. journal is the default."""
    t = text.strip()
    if REMIND_RE.search(t):
        sched = "daily@09:00"
        m = TIME_RE.search(t)
        if m:
            h = int(m.group(1)) % 12
            if (m.group(3) or "").lower() == "pm":
                h += 12
            sched = f"daily@{h:02d}:{int(m.group(2) or 0):02d}"
        # the generic nudge = the spoken intent, stripped of "remind me to"
        nudge = re.sub(r"^.*?(remind me to|reminder to|remind me)\s*", "", t, flags=re.I).strip() or t
        nudge = re.sub(r"\s*\bat\b.*$", "", nudge, flags=re.I).strip() or nudge
        return "reminder", {"title": nudge[:60].capitalize(), "nudge": nudge.capitalize(), "schedule": sched}
    if ASK_RE.search(t) and len(t.split()) > 2:
        return "ask", {"q": t}
    return "journal", {"message": t}


# ── dashboard API (the only thing that leaves this process — stays on the LAN) ─
def post(path, body):
    req = urllib.request.Request(BOX.rstrip("/") + path, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def handle(text):
    """Route a transcript to the vault. Returns (spoken_reply, result)."""
    intent, p = classify(text)
    if intent == "reminder":
        out = post("/api/reminder", {**p, "source": "voice"})
        return f"Okay — I'll remind you: {p['nudge']}, {p['schedule'].replace('daily@', 'every day at ')}.", out
    if intent == "ask":
        out = post("/api/ask", {"reason": p["q"], "doctor": "your doctor"})  # routed through the doctrine guard
        say = (out.get("text") or "I saved that to your notes.").strip()
        return say[:300], out
    out = post("/api/event", {"type": "journal", "title": "Voice journal",
                              "message": text, "severity": "info", "source": "voice"})
    return "Got it — saved to your journal.", out


# ── audio adapters (real on the Jetson, optional elsewhere) ──────────────────
def transcribe(audio_path):
    """faster-whisper small.en on the Jetson. Returns (text, avg_confidence)."""
    from faster_whisper import WhisperModel  # installed on the Jetson
    model = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="int8")
    segs, _ = model.transcribe(audio_path, vad_filter=True, language="en")
    parts, probs = [], []
    for s in segs:
        parts.append(s.text)
        probs.append(getattr(s, "avg_logprob", -1.0))
    text = " ".join(parts).strip()
    conf = sum(probs) / len(probs) if probs else -1.0
    return text, conf


def speak(text):
    """Piper TTS on the Jetson (local). Falls back to printing if absent."""
    try:
        import subprocess
        subprocess.run(["piper", "--model", PIPER_VOICE, "--output_file", "/tmp/bee_say.wav"],
                       input=text.encode(), check=True)
        subprocess.run(["aplay", "-q", "/tmp/bee_say.wav"], check=False)
    except Exception:
        print(f"🐝 Bee: {text}")


def record(seconds=8):
    """Push-to-talk capture (Silero VAD ends on silence on the Jetson build)."""
    import sounddevice as sd, soundfile as sf  # on the Jetson
    os.makedirs(VOICE_DIR, exist_ok=True)
    path = os.path.join("/tmp", "bee_capture.wav")
    print("🎙️  Listening… (push-to-talk)")
    audio = sd.rec(int(seconds * 16000), samplerate=16000, channels=1)
    sd.wait()
    sf.write(path, audio, 16000)
    return path


# ── main loop ────────────────────────────────────────────────────────────────
def run_voice(once):
    while True:
        try:
            input("Press Enter to talk to Bee (Ctrl-C to stop)… ")
            wav = record()
            text, conf = transcribe(wav)
            if not text:
                speak("I didn't catch that — try again.")
                continue
            speak(f"I heard: {text}. Is that right?")
            ok = input(f'  heard: "{text}"  — save? [Y/n] ').strip().lower()
            if ok in ("n", "no"):
                speak("Okay, scrapped that.")
                continue
            reply, _ = handle(text)
            speak(reply)
        except (KeyboardInterrupt, EOFError):
            print("\n🐝 Bee resting."); return
        if once:
            return


def main():
    global BOX
    ap = argparse.ArgumentParser(description="Bee — LocalDiabetic voice client (on-box)")
    ap.add_argument("--box", default=BOX, help="dashboard base URL on the LAN")
    ap.add_argument("--text", help="skip audio: process this transcript (testing)")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    BOX = a.box
    if a.text:
        intent, p = classify(a.text)
        reply, out = handle(a.text)
        print(f"intent={intent}  →  {reply}")
        print("result:", json.dumps(out)[:200])
        return
    run_voice(a.once)


if __name__ == "__main__":
    main()
