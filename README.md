# MedAssist Backend: Technical Core

This repository contains the central server, Machine Learning models, and OCR processing logic for the MedAssist ecosystem.

## 1. Technical Architecture

The backend is built using **Django 5.0** and **Django REST Framework (DRF)**. It emphasizes a modular service-oriented design.

### Core Modules
- **`accounts`**: Implements a Custom User model using email as the identifier. It handles Role-Based Access Control (RBAC) to ensure caretakers and patients only access relevant data.
- **`medications`**: Manages the medication registry. Includes logic for flexible frequencies and dosage parsing.
- **`adherence`**: The heart of the tracking system. It calculates adherence rates using a **Linear Decay Algorithm** (`max(0.4, 1.0 - penalty)`), tracks perfect-day streaks, and generates dynamic schedules.
- **`predictions`**: A dedicated ML service for behavioral analysis.
- **`prescriptions`**: Handles image processing and integration with Azure Cloud AI.
- **`webpush`**: Handles VAPID key signing and push subscription storage.
- **Real-Time Pulse Monitor**: Provides a persistent background listener (`--loop`) for sub-minute medication triggers.

## 2. Intelligence Layer Deep-Dive

### A. Machine Learning Pipeline (`predictions/`)
MedAssist uses a dual-model approach using **Random Forest** (via `scikit-learn`):
1.  **Feature Extraction**: For every patient-medication pair, the system generates a **17-dimensional feature vector**:
    - `avg_delay`: Calculating the mean delta between `scheduled_time` and `taken_time`.
    - `miss_rate`: The ratio of missed doses to total scheduled doses.
    - `weighted_adherence`: A 17th feature derived from the Time-Decay scoring engine (Section 12).
    - `temporal_patterns`: 7 features for day-of-week and 4 for time-of-day adherence rates.
    - `consistency`: Tracking consecutive missed doses.
2.  **Risk Classification**: The `RandomForestClassifier` labels patients as Low, Medium, or High risk based on their adherence probability.
3.  **Delay Regression**: The `RandomForestRegressor` predicts the specific delay (in minutes) for the next scheduled dose.

### B. OCR Processing Pipeline (`prescriptions/`)
The system integrates with **Azure Form Recognizer** and **Gemini AI** to automate data entry:
1.  **Image Upload**: Input is processed and stored with original metadata.
2.  **Universal Access**: The API supports both **Self-Service** scanning (for Patients) and **Managed Scanning** (for Caretakers).
3.  **Identity & Security**: Identity is resolved via JWT. Patients can only edit items within their own schedule, while Caretakers can manage their assigned patient group.
4.  **Review & Confirm**: All OCR data requires a client-side "Confirm" step before schedule injection, ensuring 100% data fidelity.

## 3. Database Schema and Relations

The system uses **PostgreSQL**. Key relationships include:
- **`User` (1) ↔ (1) `PatientProfile`**: Every patient has extended metadata (age, conditions).
- **`User` (Caretaker) (1) ↔ (N) `PatientProfile`**: One caretaker manages multiple patients.
- **`Medication` (1) ↔ (N) `AdherenceLog`**: Every log entry points back to its parent medication definition.

## 4. API Security

- **Authentication**: JWT (JSON Web Token) based.
- **Authorization**: Custom permissions (`IsCaretaker`, `IsPatient`) are enforced at the view level to prevent unauthorized data leakage.
- **Data Integrity**: All state-changing operations are wrapped in Django DB transactions to ensure log accuracy.

## 5. Development Setup

### Initialization (One-Command Setup)
MedAssist now features a unified bootstrap script for both local and production environments. From the repository root, run:

```bash
bash setup.sh
```

**What this does:**
1. Initializes the `venv` and installs `requirements.txt`.
2. Syncs the `.env` configuration.
3. Runs database migrations.
4. Seeds the database with demo accounts and retrains the ML models.
5. Launches background services (API + Voice Monitor) using Linux Screens.

## 6. Technical Implementation Guides

Detailed technical guides for core system logic:
- [**Adherence & Streak Logic**](./docs/technical-guides/adherence-algorithms.md): Weighted time-decay calculation.
- [**Voice & Notify Architecture**](./docs/VOICE_SYSTEM.md): WebPush and Live Monitor implementation.
- [**ML Feature Engineering**](./docs/technical-guides/ml-model-details.md): Model input mapping.
- [**Data Flow Trace**](./docs/technical-guides/prescription-flow-trace.md): OCR execution path.

---
*Technical Lead: Santoshi*
