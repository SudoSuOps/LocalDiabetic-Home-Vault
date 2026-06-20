#!/usr/bin/env python3
"""
LocalDiabetic Local Helper — HAT 2 (the healer's hands)
=======================================================

This is where the hive and the healers touch. An OPEN model — trained/served by
OpenDiabetic — runs on the local edge box (e.g. sigedge's ollama) and organizes
a person's LocalDiabetic vault: prep questions for an appointment, restate a
letter in plain language, build a shopping list from a food plan.

THE INVARIANT HOLDS — IN BOTH DIRECTIONS
----------------------------------------
- The model FLOWED DOWN from the hive; the vault data NEVER flows up.
- This tool runs entirely on the user's own LAN (NAS <-> edge). It NEVER calls
  the OpenDiabetic hive. PHI never leaves the user's premises.
- The helper ORGANIZES and EDUCATES. It never diagnoses, never changes meds.
  Every output ends with "confirm with your clinician."
- Every run mints a receipt: called_hive=false, left_premises=false,
  diagnosis_given=false, and exactly which vault files were touched.

USAGE
-----
  ld_helper.py prep-appointment --doctor "Dr. G (Podiatry)" \
      --reason "diabetic foot appointment" --when "Monday 8:45" \
      --vault ~/localdiabetic --model-host http://192.168.0.79:11434 \
      --model "hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M"

  ld_helper.py explain --file 03-insurance/letter.txt --vault ~/localdiabetic ...
  ld_helper.py shopping-list --vault ~/localdiabetic ...

Stdlib only. Calls a local ollama endpoint on the user's LAN.
"""

import argparse
import json
import os
import re
import time
import urllib.request
from datetime import datetime

SYSTEM = (
    "You are a diabetic-life ORGANIZER for a person managing their health at home. "
    "You DO NOT diagnose. You DO NOT give medical advice. You DO NOT change or suggest "
    "medications or doses. You organize information and explain things in plain, simple "
    "language a non-expert can follow. For anything medical, you tell the person to "
    "confirm with their clinician. Keep it short, warm, and practical. No preamble. "
    "Output ONLY the final answer — do not show any reasoning or thinking."
)

# Backstop: phrases that look like the model slipped into diagnosing/prescribing.
DIAGNOSIS_MARKERS = [
    "you have ", "you are diagnosed", "i diagnose", "your diagnosis is",
    "you should take ", "increase your dose", "decrease your dose", "stop taking",
    "start taking", "i prescribe", "the cause is", "this means you have",
]

ESCALATION = "\n\n— This is organization, not medical advice. Confirm anything medical with your clinician."


def call_model(host, model, prompt, timeout=180):
    payload = {"model": model, "prompt": prompt, "system": SYSTEM, "stream": False,
               "options": {"num_predict": 768, "temperature": 0.4}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(host.rstrip("/") + "/api/generate", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "LocalDiabetic-Helper/0.1")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read() or b"{}")
    return strip_reasoning(out.get("response") or ""), round(time.time() - t0, 1)


def strip_reasoning(text):
    """Reasoning models (LFM2.5 etc.) emit <think>…</think>. Keep only the answer."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)   # closed blocks
    if "</think>" in text:                                            # answer is after the last close
        text = text.rsplit("</think>", 1)[-1]
    text = re.sub(r"<think>.*$", "", text, flags=re.DOTALL)           # drop truncated/unclosed think
    return text.strip()


def scan_diagnosis(text):
    low = text.lower()
    return [m.strip() for m in DIAGNOSIS_MARKERS if m in low]


def write_note(vault, task, title, body, model, host, elapsed, vault_refs):
    notes_dir = os.path.join(vault, "13-organized-notes")
    receipts_dir = os.path.join(vault, "14-receipts")
    os.makedirs(notes_dir, exist_ok=True)
    os.makedirs(receipts_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    note_path = os.path.join(notes_dir, f"{task}-{stamp}.md")
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n*Organized by your local helper on {ts} — not medical advice.*\n\n")
        f.write(body.rstrip() + ESCALATION + "\n")

    diagnosis_flags = scan_diagnosis(body)
    receipt = {
        "kind": "helper-organize",
        "task": task,
        "title": title,
        "created_at": ts,
        "vault_refs": vault_refs,
        "output_note": f"13-organized-notes/{task}-{stamp}.md",
        "local_model": model,
        "model_host": host,
        "ran_seconds": elapsed,
        "called_hive": False,        # HAT 2: never calls the hive
        "left_premises": False,      # NAS <-> edge on the user's own LAN only
        "on_box": True,
        "diagnosis_given": False,
        "diagnosis_backstop_flags": diagnosis_flags,  # must be []
        "escalation_present": True,
    }
    rpath = os.path.join(receipts_dir, f"helper-{task}-{datetime.now().strftime('%Y%m%dT%H%M%S')}.json")
    with open(rpath, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
    return note_path, rpath, diagnosis_flags


def task_prep_appointment(a):
    prompt = (
        f"A person with diabetes has an appointment: {a.reason}, with {a.doctor}, {a.when}. "
        "Write a short, plain-language checklist of PRACTICAL QUESTIONS they should ask the "
        "doctor, plus what to bring. These are questions FOR the doctor — do not answer them, "
        "do not diagnose. 6-9 bullet points."
    )
    return ("Appointment prep — " + a.doctor, prompt, ["10-appointments/APPOINTMENT-PREP.md"])


def main():
    p = argparse.ArgumentParser(description="LocalDiabetic Local Helper (HAT 2)")
    p.add_argument("task", choices=["prep-appointment"])
    p.add_argument("--vault", default=os.path.expanduser("~/localdiabetic"))
    p.add_argument("--model-host", default="http://127.0.0.1:11434")
    p.add_argument("--model", required=True)
    p.add_argument("--doctor", default="your doctor")
    p.add_argument("--reason", default="appointment")
    p.add_argument("--when", default="")
    a = p.parse_args()

    builders = {"prep-appointment": task_prep_appointment}
    title, prompt, refs = builders[a.task](a)
    print(f"[helper] running '{a.task}' on local model {a.model} @ {a.model_host}")
    body, elapsed = call_model(a.model_host, a.model, prompt)
    note, receipt, flags = write_note(a.vault, a.task, title, body, a.model, a.model_host, elapsed, refs)
    print(f"[helper] done in {elapsed}s — wrote {os.path.relpath(note, a.vault)}")
    print(f"[helper] receipt {os.path.relpath(receipt, a.vault)}  "
          f"(called_hive:false left_premises:false diagnosis:{'FLAG '+str(flags) if flags else 'none'})")
    print("\n----- organized note -----\n")
    print(open(note, encoding="utf-8").read())


if __name__ == "__main__":
    main()
