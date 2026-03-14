# Technical Guide: The MedAssist Data Dictionary (Exhaustive)

This document is the definitive reference for every data field in the MedAssist ecosystem. Use this to trace variables across the frontend, backend, and mobile applications.

---

## 1. Authentication & User Management
**Django Model**: `accounts.models.User`
**Frontend Context**: `src/lib/api.ts` | `mobile-app/src/.../User.kt`

| Database Field | Type | Required | Lifecycle / Logic |
| :--- | :--- | :--- | :--- |
| `email` | `EmailField` | Yes | Primary unique identifier for login. Normalized on save. |
| `name` | `CharField(255)` | Yes | Display name shown in all headers and patient lists. |
| `role` | `CharField(10)` | Yes | `caretaker` or `patient`. Dictates permissions and dashboard routing. |
| `phone` | `CharField(20)` | No | Stored with a blank default; intended for future SMS notification hooks. |
| `password` | `Hash` | Yes | Never stored in plain text. Hashed using Django's default PBKDF2 with a salt. |
| `is_active` | `Boolean` | Yes | Default `True`. Can be toggled to disable access without deleting data. |
| `created_at` | `DateTimeField` | Auto | Timestamp of account creation. |

---

## 2. Patient Profiles
**Django Model**: `medications.models.PatientProfile`
**Relationship**: `OneToOneField(User)`

This model extends the `User` model specifically for roles marked as `patient`.

| Database Field | Type | Description |
| :--- | :--- | :--- |
| `user` | `User` | FK to the base User record (the patient themselves). |
| `age` | `PositiveInt` | Patient's age (optional). Used as a feature in future ML iterations. |
| `medical_conditions`| `TextField` | Free-text area for relevant medical history (Chronic diseases, Allergies). |
| `caretaker` | `User` | FK to the User marked as `caretaker` who manages this patient. |
| `adherence_rate` | `MethodField` | **DYNAMIC**: Calculated as `(taken + late) / total * 100`. |

---

## 3. Medication & Prescriptions
**Django Models**: `medications.models.Medication`, `prescriptions.models.Prescription`

| Model Field | Type | Source | Logic / Transformation |
| :--- | :--- | :--- | :--- |
| `name` | String | OCR / Manual | Extracted by Gemini from Azure OCR text blocks. |
| `dosage` | String | OCR / Manual | e.g. "500mg". Parsed from prescription lines. |
| `frequency` | String | OCR / Manual | Choices: `once_daily`, `twice_daily`, `thrice_daily`, `custom`. |
| `timings` | `JSONField` | UI Picker | A list of HH:MM strings: `["08:00", "20:00"]`. |
| `instructions` | `TextField` | Manual | Supplementary notes (e.g., "Take after meals"). |
| `is_active` | `Boolean` | System | If `False`, the medication is filtered out of "Today's Schedule". |
| `extracted_data` | `JSONField` | OCR Engine | Raw JSON from Gemini stored in the `Prescription` model for audit. |

---

## 4. Adherence Logs (The Core Data)
**Django Model**: `adherence.models.AdherenceLog`

| Model Field | Type | Logic |
| :--- | :--- | :--- |
| `medication` | FK | Links to the specific medication definition. |
| `patient` | FK | Links to the `User` record of the patient. |
| `scheduled_time` | `DateTimeField` | When the patient WAS supposed to take it (generated from `timings`). |
| `taken_time` | `DateTimeField` | When the patient ACTUALLY clicked "Take". Can be null if `missed`. |
| `status` | `Choice` | `taken` (on time), `late` (>1hr deviation), `missed` (>4hr deviation). |

---

## 5. ML Predictions & Risks
**Django Model**: `predictions.models.Prediction`

| Model Field | Type | Transformation Logic |
| :--- | :--- | :--- |
| `risk_level` | Choice | `low`, `medium`, `high`. Based on `miss_rate` thresholds. |
| `predicted_delay_minutes` | `Int` | Output from the RandomForestRegressor model. |
| `message` | `TextField` | Human-friendly summary of the AI's findings. |

---
### Data Ownership Summary:
- **Caretakers**: Own the `Medication` creation logic and `PatientProfile` assignments.
- **Patients**: Own the `AdherenceLog` creation (intake events).
- **System**: Owns the `Prediction` generation and `Today's Schedule` dynamic builder.
