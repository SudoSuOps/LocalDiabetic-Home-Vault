# The Hard Invariant — OpenDiabetic Law

This is not a setting. It is the law the whole system is built around.

---

## The invariant

> **Raw personal health records never auto-flow to the OpenDiabetic cloud.**

- The NAS (your home box) is the vault.
- **The user owns the records.** Always. Without exception.
- The cloud may receive only: receipts, model updates, templates, open datasets,
  and non-PHI operational metadata.
- **Any** export of personal health information (PHI) must be:
  1. **Explicit** — the user chooses it, deliberately.
  2. **User-approved** — never automatic, never a default, never buried in a toggle.
  3. **Logged** — recorded in `14-receipts/`.
  4. **Receipt-backed** — a verifiable record of what left, when, and why.

---

## Why this is the moat

This single architectural choice does three jobs at once:

**Product** — It is the trust story no extractive health-tech company can copy.
Your records stay with you. The vault is yours. The cloud never sees your papers.

**HIPAA** — A tool that helps a person organize *their own* records on *their own*
box is a filing cabinet, not a covered entity. The moment PHI is aggregated
server-side, the system becomes a HIPAA business associate and the cost and risk
multiply. We do not cross that line.

**FDA** — Local-first, organization-only, with "confirm with your clinician"
escalation language, keeps us out of medical-device regulation. The vault organizes
and reminds. It does not interpret medicine.

---

## What the cloud is allowed to see

| Allowed to cloud | Never to cloud (stays on the NAS) |
|---|---|
| Receipts (proof of action, no PHI) | Discharge papers, lab results, records |
| Model updates / new templates | Medication lists tied to a person |
| Open, non-personal datasets | Insurance member IDs, doctor notes |
| Operational metadata (counts, uptime) | Anything that identifies the diabetic |

---

## The rule for every AI action

Every automated action on a user's behalf gets a receipt in `14-receipts/` proving:

- What was requested
- What data was touched (and that it stayed local)
- What was produced
- That **no diagnosis** was given
- That **escalation language** ("confirm with your clinician") was present
- That the user approved
- Where the result was stored

**We don't judge. We apply a declared rulebook and throw a flag if it's violated.**
The referee model never opines on medicine — it checks that the boundaries held.

---

*If a feature cannot honor this invariant, the feature does not ship. Full stop.*
