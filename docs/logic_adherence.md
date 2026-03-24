# Adherence Logic Deep-Dive

This document explains the mathematical and logical implementation of patient adherence tracking in MedAssist.

## 1. Data Model: `AdherenceLog`
Every time a patient is supposed to take a medication, the system (eventually) creates an `AdherenceLog` entry. 

- **Status types**:
    - `taken`: Patient took the med on time.
    - `late`: Patient took the med, but after the scheduled window.
    - `missed`: The scheduled time has passed and no action was taken.

---

## 2. Calculating the Adherence Rate (Linear Decay)
**Location**: `backend/adherence/utils/rates.py` -> `calculate_adherence_rate()`

The Adherence Rate is no longer a simple percentage. We use a **Linear Decay Formula** to give partial credit for late doses.

**The Formula**:
1. **Dose Penalty**: `penalty = hours_late * 0.1` 
2. **Dose Score**: `score = max(0.4, 1.0 - penalty)`
3. **Cumulative Rate**: `(Sum of Scores / Total Expected Doses) * 100`

*Example*: If a med is 2 hours late, the patient gets **80% credit** for that dose. This provides a much more sensitive health metric for the ML model.*

---

## 3. The Streak Algorithm
MedAssist tracks two types of streaks: **Current Streak** and **Longest Streak**. A streak is defined by "Perfect Days"—days where *every* scheduled medication was marked as `taken`.

### How it works Step-by-Step:
1. **Gather Logs**: We fetch all logs for the patient and sort them by date.
2. **Determine Daily Status**: We create a map where each key is a `Date`.
   - If *all* logs for a date are `taken`, the date is marked `True`.
   - If *any* log for a date is `missed` or `late`, the whole date is marked `False`.
3. **Calculating Longest Streak**:
   - We iterate through the sorted dates.
   - We increment a `temp_counter` for every `True` date.
   - We update `longest_streak = max(longest_streak, temp_counter)`.
   - If we hit a `False` date, `temp_counter` resets to 0.
4. **Calculating Current Streak**:
   - we iterate **backwards** from today.
   - We increment the counter until we hit a `False` date or a gap in the timeline.

---

## 4. Today's Schedule Generation
**Location**: `backend/adherence/views.py` -> `TodayScheduleView`

The schedule isn't just a static list; it's dynamically generated every time the user opens the app.

1. **Fetch Active Meds**: Get all medications where `is_active=True`.
2. **Parse Timings**: Every medication has a `timings` JSON field (e.g., `["08:00", "20:00"]`).
3. **Cross-Reference Logs**:
   - The system looks at today's `AdherenceLog` entries.
   - It matches the `medication_id` and the `time` string.
4. **Define Status**:
   - If a log exists, it uses that status.
   - If no log exists for that specific time today, it defaults to `pending`.

---

## 5. Why this matters for the Frontend
The frontend uses these stats to show the "Health Score" of the patient. If the `current_streak` is high, the caretaker sees a "Good" status. If the `adherence_rate` drops below 70%, the system flags the patient for review.
