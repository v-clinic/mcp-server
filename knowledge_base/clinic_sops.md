# vClinic Standard Operating Procedures (SOPs)
## Operations & Clinical Administration | Revision: 2026-01

---

## SOP-001: Patient Registration and Check-In

### Purpose
Ensure accurate and consistent patient registration to maintain data integrity and continuity of care.

### Procedure

**New Patients**
1. Collect full legal name, date of birth, sex at birth, gender identity, preferred pronouns
2. Record government-issued ID and insurance card (scan into EMR)
3. Obtain and verify emergency contact (name, relationship, phone)
4. Collect all known drug allergies with reaction type (anaphylaxis, rash, GI intolerance)
5. Review and update medication list (reconcile with pharmacy records if available)
6. Assign primary care provider (PCP) if none designated
7. Obtain signed consent for treatment and HIPAA acknowledgment
8. Assign patient_id in EMR system; never reuse or duplicate IDs

**Returning Patients**
1. Verify identity using two identifiers: name + DOB (never room number or diagnosis)
2. Confirm insurance status and co-pay eligibility
3. Update medication list, allergies, and emergency contact if changes reported
4. Verify preferred pharmacy if new prescriptions anticipated

### Escalation
- Unaccompanied minors (<18): notify supervisor; do not register without guardian consent except emergencies
- Patients presenting with altered mental status: notify clinical staff immediately

---

## SOP-002: Vital Signs Documentation

### Purpose
Standardize vital sign collection and documentation for all patient visits.

### Required Vitals (All Visits)
| Parameter | Method | Normal Range (Adult) |
|-----------|--------|---------------------|
| Blood Pressure | Automated or manual (right arm at rest ≥5 min) | <120/80 mmHg |
| Heart Rate | 60-second radial pulse or automated | 60–100 bpm |
| Respiratory Rate | Counted over 60 seconds (do not estimate) | 12–20 breaths/min |
| Temperature | Oral preferred; document route | 36.1–37.2°C / 97–99°F |
| SpO2 | Pulse oximetry, right index finger | ≥95% |
| Weight | Digital scale, shoes removed | — |
| Height | First visit or annually | — |

### Documentation Format (EMR vital_signs field)
Always record as JSON:
```
{"bp":"120/80","temp":98.6,"hr":72,"rr":16,"spo2":98,"weight_kg":70,"height_cm":170}
```

### Critical Vital Signs — Immediate Escalation Required
- SpO2 < 90%: Administer supplemental O2, notify physician immediately
- SBP > 180 or < 80 mmHg: Notify physician before patient enters room
- HR > 130 or < 45 bpm: Notify physician immediately
- RR > 25 or < 8: Notify physician immediately
- Temp > 40°C (104°F): Notify physician immediately

---

## SOP-003: Lab Order and Collection Procedures

### Ordering Requirements
- All lab orders must include:
  - Patient ID and visit ID
  - Ordering physician name and staff ID
  - Clinical indication in the notes field (e.g., "R/O pneumonia, evaluate WBC/CRP")
  - Priority: STAT (results within 1 hour), Routine (4–6 hours)

### Common Panel Reference

**CBC with Differential** (`CBC_DIFF`)
- Tube: Purple EDTA (3 mL)
- Normal ranges (adults): WBC 4.5–11.0 × 10³/μL; RBC 4.2–5.4 M/μL; Hgb 12–17 g/dL; Hct 36–51%; Plt 150–400 × 10³/μL; Neutrophils 50–70%; Lymphocytes 20–40%
- Critical values: WBC > 30 or < 2 × 10³/μL; Hgb < 7 g/dL; Plt < 50 × 10³/μL

**BMP (Basic Metabolic Panel)** (`BMP`)
- Tube: Green SST (5 mL)
- Normal ranges: Na 136–145 mEq/L; K 3.5–5.0 mEq/L; Cl 96–106 mEq/L; CO2 22–29 mEq/L; BUN 7–25 mg/dL; Creatinine 0.6–1.2 mg/dL (male), 0.5–1.1 mg/dL (female); Glucose 70–100 mg/dL (fasting)
- Critical values: K < 2.8 or > 6.5; Na < 120 or > 160; Glucose < 50 or > 500

**CRP (C-Reactive Protein)** (`CRP`)
- Tube: Red SST (3 mL)
- Normal: < 10 mg/L; Elevated infection/inflammation: > 10 mg/L; Severe: > 100 mg/L

**HbA1c** (`HBA1C`)
- Tube: Purple EDTA (no fasting required)
- Normal: < 5.7%; Pre-diabetes: 5.7–6.4%; Diabetes: ≥ 6.5%

**Urinalysis with Microscopy** (`UA_MICRO`)
- Container: Clean-catch midstream urine in sterile cup
- Significant bacteriuria: ≥ 10⁵ CFU/mL (culture threshold)

**Blood Culture** (`BLOOD_CULTURE`)
- Two sets from two different sites (aerobic + anaerobic bottles)
- Collect before antibiotic administration whenever possible
- Indication: fever + suspected bacteremia, immunocompromised

### Critical Value Notification
- Lab calls physician directly for critical values
- Physician must acknowledge and document action taken within 30 minutes
- If physician unreachable: escalate to charge nurse

---

## SOP-004: Radiology Ordering Procedures

### Indications and Appropriate Use

**Chest X-Ray (CXR)** (`CHEST_XRAY`)
- Indications: cough > 3 weeks, dyspnea, suspected pneumonia, pleuritic chest pain, hemoptysis, pre-op
- Order: PA + Lateral if ambulatory; AP portable if bedridden
- Expected turnaround: Routine 4–6h; STAT 1h

**Abdominal X-Ray (KUB)** (`AXR_KUB`)
- Indications: suspected bowel obstruction, renal calculi, foreign body
- Note: Low sensitivity for many conditions; CT abdomen preferred if high suspicion obstruction

**CT Abdomen & Pelvis with Contrast** (`CT_ABD_PELVIS`)
- Indications: RLQ pain (appendicitis r/o), diverticulitis, renal/ureteral stones, abdominal mass
- Requires: Creatinine ≤ 1.5 mg/dL and no allergy to IV contrast before ordering with contrast
- Hold metformin 48h before and after IV contrast if eGFR < 60

**Abdominal Ultrasound** (`US_ABDOMEN`)
- Indications: RUQ pain (gallstones, cholecystitis), hepatomegaly, splenomegaly, ascites
- Order fasting (NPO 4–6h for gallbladder imaging)

**ECG / EKG** (`ECG_12LEAD`)
- Indications: chest pain, palpitations, syncope, new HTN diagnosis, pre-op ≥40 years, known heart disease
- Turnaround: STAT 15 minutes

### Radiology Report Review
- Physician must acknowledge and act on all radiology reports within 4 hours (routine) or immediately (STAT/critical)
- Critical findings (tension pneumothorax, aortic dissection, PE, subarachnoid hemorrhage): radiologist calls physician directly
- Incidental findings requiring follow-up: document in Assessment/Plan with patient notification within 5 business days

---

## SOP-005: Prescription and Treatment Documentation

### Prescribing Requirements
- All prescriptions must include: drug name, dose, route, frequency, duration, quantity, refills
- Verify allergies before prescribing: system will flag; physician must acknowledge override
- Controlled substances: comply with state PDMP lookup before prescribing Schedule II–IV drugs
- Antibiotics: document indication, duration, and anticipated clinical endpoint

### Medication Reconciliation
- Reconcile medications at every visit (add, discontinue, or continue with dose changes documented)
- Flag drug-drug interactions flagged by the pharmacy system
- Patient education: provide written instructions for all new medications

### Treatment Plan Documentation Requirements
- Each treatment record must include:
  - Treatment type: medication, procedure, referral, or lifestyle
  - For medications: name, dose, frequency, duration
  - For referrals: specialty, urgency (routine vs. urgent vs. emergent), clinical reason
  - For procedures: procedure name, indication, consent obtained
  - For lifestyle: specific, actionable instructions (not just "diet and exercise")

---

## SOP-006: Visit Closure and Discharge

### Requirements Before Closing a Visit
- [ ] All lab and radiology results reviewed and documented in the chart
- [ ] Final (non-preliminary) diagnosis documented with ICD-10 code
- [ ] Treatment plan finalized and documented
- [ ] Medication changes reconciled
- [ ] Follow-up plan documented (date, provider, reason)
- [ ] Patient education provided and documented
- [ ] Discharge summary written in the visit notes

### Discharge Summary Format
The discharge summary in the visit notes field should include:
1. **Presenting complaint**: brief statement
2. **Findings**: key exam findings, relevant vital signs, lab/imaging results
3. **Diagnosis**: final diagnosis with ICD-10 code
4. **Treatment**: medications prescribed, procedures performed
5. **Instructions**: diet, activity, wound care, medication schedule
6. **Return precautions**: specific symptoms that warrant return visit or ED
7. **Follow-up**: date, provider, what to monitor

### Visit Status Codes
- `open` — visit in progress; patient in clinic
- `pending_results` — awaiting lab or radiology results
- `closed` — all results reviewed; treatment complete; discharge summary written
- **Do NOT close a visit with pending results unless explicitly documented why** (e.g., results not clinically necessary after diagnosis confirmed by other means)
