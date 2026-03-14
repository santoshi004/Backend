# Technical Guide: Adherence & Streak Algorithms (Exhaustive)

This document explains the deep numerical logic used to calculate patient health metrics in MedAssist.

---

## 1. The Adherence Score Logic
**Reference**: `backend/medications/serializers.py` -> `get_adherence_rate()`

The score is a cumulative metric representing overall compliance.

### The Math:
1. **Fetch Logs**: Filter `AdherenceLog` by the specific `patient`.
2. **Success Count**: Count all entries where `status` is either `taken` OR `late`.
3. **Total Count**: Count *all* entries in the log history.
4. **Percentage**: `(Success / Total) * 100`.

*Developer Note: We count "Late" as a success for the general rate because the medication was still consumed, but it is penalized in the "Risk Prediction" ML model.*

---

## 2. The Streak Algorithm (The "Perfect Day" logic)
**Reference**: `backend/adherence/views.py` -> `AdherenceStatsView.get`

A streak is NOT based on individual doses, but on **Perfect Days**. 

### Step 1: Normalization and Validation
The code creates a dictionary where each key is a unique **Date**:
```python
dates_with_logs = {}
for log in logs:
    date_key = log.scheduled_time.date()
    # Initialize as True (Perfect)
    if date_key not in dates_with_logs:
        dates_with_logs[date_key] = True
    # Invalidation: If ANY dose on this date was missed or late
    if log.status != 'taken':
        dates_with_logs[date_key] = False
```

### Step 2: Historical Peak (Longest Streak)
We iterate through the sorted list of dates:
- If a date is `True`, `temp_streak` increases by 1.
- `longest_streak` is updated using `max(longest_streak, temp_streak)`.
- If a date is `False`, `temp_streak` resets to 0.

### Step 3: Predictive Persistence (Current Streak)
We iterate **backwards** from the latest logged date:
- Count consecutive `True` dates.
- Stop immediately when a `False` date or a "Gap" (a day with no logs) is found.

---

## 3. Dynamic Schedule Generator
**Reference**: `backend/adherence/views.py` -> `TodayScheduleView`

MedAssist does not store a "Tomorrow" schedule. It builds it on-the-fly when requested.

1. **Timings Pull**: Pulls the `timings` list (e.g., `["08:00", "22:00"]`) from the active `Medication` records.
2. **Construction**: For "Today," it combines the Date with each Timing string to create a `scheduled_dt`.
3. **Matching**: It performs a filtered query on `AdherenceLog` for today's date and links the logs to the generated times.
4. **Defaulting**: If no log exists for a specific timing, it defaults the status to `pending` in the JSON response.

---

## 4. State Transitions & Edge Cases
| Status | Time Logic | Description |
| :--- | :--- | :--- |
| `pending` | `Now < ScheduledTime` | Medication is due in the future. |
| `taken` | `Within 60 mins` | Recorded as a successful on-time intake. |
| `late` | `> 60 mins after` | Patient forgot but took it eventually. Resets daily streak. |
| `missed` | `> 4 hours after` | Dose completely skipped. Triggers high-risk flag. |

---
### Technical Summary for Student Presenters:
> "Our logic is derived asynchronously. Instead of storing complex schedules, we store 'Patterns' (Timings) and 'Events' (Logs). This allows us to calculate health metrics like 'Streaks' dynamically, ensuring the data is always mathematically sound regardless of timezone or day shifts."
