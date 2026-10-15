# REVIEW.md

## Defects Found in the Starter `app/main.py`

| # | Where (function / line) | What is wrong | How you'd notice it (test, input, or symptom) | How you fixed it |
|---|---|---|---|---|
| 1 | `create_employee()` and employee indexes | Checking whether an employee exists before insertion is insufficient under concurrent requests. | Send simultaneous requests creating the same employee code. | Added a unique index on `employees.emp_code` and handled `DuplicateKeyError` with HTTP 409 Conflict. |
| 2 | `punch_in()` and attendance indexes | Two simultaneous punch-in requests can both pass the initial existence check, creating duplicate attendance records without database enforcement. | Send concurrent punch-in requests for the same employee and attendance date. | Added a unique compound index on `attendance_logs.emp_code` and `date`; duplicate insert attempts are handled as conflicts. |
| 3 | `PunchIn`, `PunchOut`, and `punch_in()` | Timestamp inputs require strict validation. Seconds instead of milliseconds, strings, floats, out-of-range values, and explicitly supplied null values can cause invalid processing. | Test invalid types, timestamp boundaries, omitted timestamps, and explicit null values. | Added strict integer validation and numeric bounds, with explicit-null handling for the punch-in timestamp. |
| 4 | `punch_out()` | Elapsed-time calculations must use consistently initialized values for both supplied and default timestamps. | Test punch-out with and without an explicitly supplied timestamp; check for unexpected HTTP 500 responses. | Ensure elapsed duration and its derived values are initialized consistently before subsequent calculations. |
| 5 | Timestamp conversion and attendance-date calculation | UTC timestamps and the intended attendance timezone can produce different calendar dates. | Test timestamps close to midnight in UTC and IST. | Use consistent timezone conversion when deriving attendance dates and calculating attendance values. |
| 6 | Work-hour and overtime calculation helpers | Invalid durations and inconsistent rounding can produce incorrect derived attendance values. | Test zero or negative durations, long shifts, and rounding boundaries. | Validate elapsed durations and apply consistent rounding and business-rule calculations. |
| 7 | Department summary aggregation | Starting from attendance records alone can exclude employees who have no attendance logs from department headcount. | Create an employee without attendance records and request the department summary. | Start from employees and preserve unmatched lookup results so employees without logs remain represented. |
| 8 | Late-arrival leaderboard aggregation | Applying a simple result limit can exclude employees tied at the cutoff. | Create multiple employees with equal late-minute totals at the requested leaderboard limit. | Use ranking semantics so employees tied at the cutoff can be included. |
| 9 | Analytics aggregation and explain endpoints | Query-plan inspection must use the correct aggregation command and return execution statistics in the expected response contract. | Call each explain endpoint and validate its response; inspect execution statistics for index usage. | Review aggregation explain-command construction and endpoint response handling. Further verification is required for all analytics explain endpoints. |

## Items Reviewed and Not Considered Defects

| # | Where (function / line) | What was examined | Why it was not considered a defect |
|---|---|---|---|
| 1 | Employee and attendance indexes | Unique constraints on employee codes and employee/date attendance combinations. | These constraints provide database-level protection against duplicate records, including concurrent insertion attempts. |
| 2 | Department summary aggregation | Use of `$lookup` and preservation of unmatched employee records. | Preserving unmatched results allows employees without attendance logs to contribute to department headcount. |
| 3 | Late-arrival leaderboard | Ranking employees with equal late-minute totals. | Including ties at the cutoff is a valid ranking policy, even if the response contains more records than the requested limit. |
| 4 | Aggregation pipelines | Use of MongoDB aggregation for analytics calculations. | Aggregation pipelines are appropriate for database-side summaries; their performance still needs to be verified against representative data. |
| 5 | Environment configuration | MongoDB connection URI and database name supplied through environment variables. | External configuration avoids hard-coding deployment-specific connection details in application code. |

## Remaining Verification

The items above describe the defects and safeguards identified during development. The following areas still require verification against the assignment contract and target MongoDB environment:

- Concurrent punch-out behavior.
- Correct response contracts for all explain endpoints.
- Index usage and execution statistics on representative large datasets.
- Full coverage of the supplied business rules and edge cases.