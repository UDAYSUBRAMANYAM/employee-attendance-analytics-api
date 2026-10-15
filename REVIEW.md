# REVIEW.md

List every defect you found in the starter `app/main.py` (helpers and endpoints). For each one:

| # | Where (function / line) | What is wrong | How you'd notice it (test, input, or symptom) | How you fixed it |
|---|---|---|---|---|
| 1 | Employee uniqueness and duplicate creation
Location: create_employee() and employee indexes.
Issue: Checking for an existing employee before inserting is not sufficient under concurrent requests.
Fix: A unique index on employees.emp_code enforces uniqueness in MongoDB. DuplicateKeyError is caught and returned as 409 Conflict. 
| 2 | Duplicate attendance records
Location: punch_in() and attendance indexes.
Issue: Two simultaneous punch-in requests can both pass an initial existence check.
Fix: A unique compound index on attendance_logs.emp_code and date makes the database enforce one record per employee per attendance date. Duplicate insert attempts return 409 Conflict.

| 3 | Timestamp validation
Location: PunchIn, PunchOut, and punch_in().
Issue: Timestamps must be epoch milliseconds, not seconds, strings, floats, or out-of-range values. Explicit null timestamps also need to be distinguished from omitted timestamps.
Fix: Strict integer validation and numeric bounds are applied. The punch-in model rejects an explicitly supplied null timestamp while retaining the omitted-timestamp default.


| | | |

Also note anything you looked at and decided was **not** a defect, and why.
