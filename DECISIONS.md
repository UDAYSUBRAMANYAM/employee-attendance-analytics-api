# DECISIONS.md

## 1. Indexes

A unique index on `employees.emp_code` supports employee identification and prevents duplicate employee codes. A unique compound index on `attendance_logs.emp_code` and `date` is intended to enforce one attendance record per employee per day. An additional index on `attendance_logs.date` in descending order and `emp_code` in ascending order supports date-oriented queries and sorting.

I did not add a department-specific compound index without first establishing that it improves the relevant query plans. Indexes consume storage and increase write costs, so additional indexes should be justified by query patterns and execution statistics.

## 2. Simultaneous Punch-In Requests

Two requests can both check for an existing attendance record before either inserts it. An application-level existence check alone cannot prevent this race condition. The unique compound index on employee code and date provides the database-level integrity constraint. Duplicate-key errors should be handled as conflicts rather than allowing duplicate attendance records.

## 3. Leaderboard Ties

The leaderboard uses MongoDB ranking semantics. Employees with the same total late minutes can receive the same rank. Filtering by rank up to the requested limit can return more employees than the limit when multiple employees tie at the cutoff. This behavior preserves ties instead of arbitrarily excluding employees with equal scores.

## 4. Employees Without Attendance Logs

The department summary begins with employees and joins attendance records using `$lookup`. Preserving unmatched records with `preserveNullAndEmptyArrays: true` allows employees without attendance logs to remain in the aggregation. They can therefore contribute to department headcount even when they have no recorded attendance.

## 5. Scaling to 100× the Dataset

I would benchmark representative workloads using MongoDB execution statistics, inspect index usage, and optimize expensive aggregation stages. I would evaluate compound indexes against actual filters and sort operations rather than adding indexes indiscriminately. If analytics become expensive at larger scale, I would consider pre-aggregated summaries or scheduled materialization, while accounting for freshness requirements and additional operational complexity.