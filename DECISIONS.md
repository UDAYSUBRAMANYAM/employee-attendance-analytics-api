# DECISIONS.md  (about 150-200 words in total - plain language, your own words)

1. **Indexes.** Which indexes did you create, and which query or guarantee does each one serve? Which one did you consider and reject?

Created a Unique index onemployees.emp_code cuz it is the business identifier and must never be duplicated. i created a unique compound index on attendance_logs.emp_code and date to enforce one attendance record per employee per day.  also created an index attendance_logs.date ascending to support date oriented attendance query on sorting
2. **Punch-in race.** Two identical punch-in requests arrive at the same instant. Walk through exactly what happens in your code.
    Two requests can both check for an existing record and initially find none. Both then attempt insertion, but the unique compound index allows only one record for that employee and date. one will be stored and the 201 ok sent then the second request will fail because of DuplicateKeyError and returns 409 Conflict.

3. **Ties.** Two employees are tied on late minutes at the cutoff of `limit`. What does your leaderboard return, and why?

    The leaderboard uses MongoDB $rank on total late minutes and filters ranks up to the requested limit. Employees tied at the cutoff can therefore all be included, so the response may contain more than the requested limit.

4. **Headcount.** How does your department summary make sure employees with zero logs are counted?

    The leaderboard uses MongoDB $rank on total late minutes and filters ranks up to the requested limit. Employees tied at the cutoff can therefore all be included, so the response may contain more than the requested limit.

5. **One thing you would change** if this had to serve 100x the data.
    I would benchmark explain plans on representative data, add indexes supported by those plans, and review aggregation costs. I would also consider moving analytics to pre-aggregated summaries if real query workloads justify the added complexity.