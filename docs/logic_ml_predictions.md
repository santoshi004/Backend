# Machine Learning & AI Deep-Dive

This document explains how MedAssist uses artificial intelligence to predict patient risks.

## 1. The Strategy: "Random Forest"
MedAssist uses **Random Forest** algorithms via the `scikit-learn` library. We use two models:
1. **Classifier**: To determine the Risk Category (Low/Medium/High).
2. **Regressor**: To predict the exact number of minutes a patient might be late.

---

## 2. Feature Engineering (The "Input")
Before the model can predict anything, we must convert raw `AdherenceLog` data into numbers the computer understands. We extract **16 Features**:

| Feature Name | Description | Why it matters |
| :--- | :--- | :--- |
| `avg_delay` | Average minutes late | Shows general punctuality. |
| `miss_rate` | % of missed doses | Primary indicator of high risk. |
| **`weighted_adherence`** | **17th Feature** | The Time-Decayed score (Section 2 of Adherence Guide). |
| `consecutive_misses` | Max missed in a row | Shows if the patient has "abandoned" the med. |
| `day_pattern_0-6` | Adherence rate per day | Detects "Weekend" vs "Weekday" issues. |
| `time_pattern_*` | Rate for Morning/Night | Detects "Sleeping through dose" issues. |

---

## 3. How the Model Learns
**File**: `backend/predictions/services/ml_service.py` -> `train_models()`

1. **Baseline**: The model looks at all historical data for the patient.
2. **Branching**: A Random Forest creates multiple "Decision Trees." 
   - *Example Tree*: `IF miss_rate > 0.4 AND consecutive_misses > 2 -> THEN Risk = High`.
3. **Ensemble**: It combines the answers from 100 different trees to get the most accurate result.

---

## 4. Rule-Based Fallback
**What happens if a new patient has 0 data?**
ML models need data to work. If a patient has fewer than 5 logs, the system switches to a **Rule-Based Engine**:
- **High Risk**: If `miss_rate` > 40%.
- **Medium Risk**: If `miss_rate` > 15% OR `avg_delay` > 30 mins.
- **Low Risk**: Everyone else.

*This ensures the system is "Smart" from Day 1, even before the AI is fully trained.*

---

## 5. Integration with OCR
The `prescriptions` module uses **Azure Form Recognizer** to turn images into text. 
1. **OCR Proxy**: We don't write our own AI for images; we use Azure's world-class model.
2. **Gemini Refinement**: We use Google's **Gemini-2.0-Flash** to take the raw text from Azure and "clean it up" into perfect JSON that our database can save.
