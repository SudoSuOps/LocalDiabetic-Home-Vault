# Receipts

**Proof, not promises.** Every automated action on your behalf leaves a receipt here.

---

## What a receipt is

A receipt is a small, plain record of something the system did for you. It exists so
you (or a family member, or an auditor) can see exactly what happened — without
taking anyone's word for it.

Every receipt answers:

- **What was requested?**
- **What data was touched** — and did it stay local? (It should always say *yes*.)
- **What was produced?**
- **Was any diagnosis given?** (Must be *no*.)
- **Was "confirm with your clinician" language present?** (Must be *yes* when relevant.)
- **Did the user approve?**
- **Where was the result stored?**

## Example receipt

```json
{
  "receipt_id": "ld-0001",
  "action": "build-shopping-list",
  "requested_by": "user",
  "data_touched": ["09-food-cookbooks/food-plan.md"],
  "left_the_vault": false,
  "produced": "13-organized-notes/shopping-list-2026-06-20.md",
  "diagnosis_given": false,
  "clinician_escalation_present": true,
  "user_approved": true,
  "timestamp": "<set when the action runs>"
}
```

## The rule

> **We don't judge. We apply a declared rulebook and throw a flag if it's violated.**

The receipt is how we prove the boundaries held — that the vault stayed local, that
no medicine was interpreted, that you stayed in control. This is the same Defendable
receipt discipline used across the whole house, pointed at diabetic life.

See `../HARD-INVARIANT.md` for the law these receipts enforce.

---

*If an action can't produce an honest receipt, it shouldn't run.*
