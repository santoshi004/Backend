# Technical Guide: ML Feature Engineering & Analytics (Advanced)

This document provides a exhaustive breakdown of how patient behavior is transformed into predictive risk data.

---

## 1. Feature Engineering (The 16 Dimensions)
A Machine Learning model is only as good as the numbers it reads. We transform raw `AdherenceLog` records into a fixed-length vector of **16 features**.

**Code Reference**: `backend/predictions/services/ml_service.py` -> `_extract_features()`

### Behavioral Constants (5 Features)
1.  **`avg_delay`**: Mean deviation in minutes for all non-missed doses.
2.  **`miss_rate`**: `missed_count / total_count`.
3.  **`late_rate`**: `late_count / total_count`.
4.  **`consecutive_misses`**: The maximum streak of `missed` status logs.
5.  **`total_logs`**: The count of events (serves as the "experience" level of the model).

### Temporal Patterns (11 Features)
- **`day_pattern_0-6`**: Percentage of success for each day from Monday (0) to Sunday (6).
  - *Why?*: Detects users who struggle on weekends vs. weekdays.
- **`time_pattern_morning/afternoon/evening/night`**: Percentage of success in 4-hour windows.
  - *Why?*: Identifies users who miss "Morning" doses (oversleeping) vs. "Night" doses.

---

## 2. Model Architecture
MedAssist uses a **Dual RandomForest System**.

### A. The Risk Classifier (`risk_classifier.pkl`)
- **Type**: RandomForestClassifier
- **Goal**: Predict a label (`low`, `medium`, `high`).
- **Learning**: It maps the 16 features against a ground-truth "Health Grade" during the training phase.

### B. The Delay Regressor (`delay_regressor.pkl`)
- **Type**: RandomForestRegressor
- **Goal**: Predict a continuous value (minutes).
- **Learning**: It correlates behavioral delay patterns with the most likely delay for the next dose.

---

## 3. The Lifecycle of a Prediction
1. **Trigger**: Caretaker visits a Dashboard.
2. **Extraction**: The `ml_service` pulls all logs for the patient.
3. **Imputation**: If a feature is missing (e.g., no logs for "Monday"), the system defaults it to `1.0` (assume good behavior) to prevent model bias.
4. **Execution**: The models are loaded from disk (`.pkl` files) and the `predict()` function is called.
5. **Persistence**: The results are saved to the `Prediction` model and sent to the frontend.

---

## 4. Rule-Based Fallback (The "Zero-Data" Guard)
**Reference**: `_rule_based_prediction()`

When the ML models lack sufficient training data (less than 5 logs), we use fixed logic:
- **High Risk**: If `miss_rate` > 40% OR `consecutive_misses` >= 5.
- **Medium Risk**: If `miss_rate` > 15% OR `avg_delay` > 30 minutes.
- **Low Risk**: Standard compliance.

---
### Technical Summary for Student Presenters:
> "We transform subjective human behavior into 16 objective mathematical features. This allows our Random Forest models to detect patterns that are invisible to a human caretaker—such as a specifically declining adherence on Tuesday afternoons."
