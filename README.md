# Simple shift calculator

This is a quite hardcoded shift calculator using Googles OR-Tools. Each day consists of shifts with different worktimes. The goal is to dynamically create shift-table for each employee. There are some additional there are some constrains which should be respected. At the moment four shfits are hardcoded.

## hardcoded shifts
day_shift (d) ... each day ... 14:00 - 20:00
normal_nightshift (n) ... sunday, monday ... 13:00 - 13:30 (next day)
hwk_nightshift (nhwk) ... tuesday, wednesday, thursday ... 13:00 - 09:00 (next day)
weekend_nightshift (wn) ... friday, saturday ... 13:00 - 13:30 (next day)

**Note:** the 'next day' at n and 'nhwk' starts at 05:00 while at 'wn' at 06:00.

On the first startup two configuration files are created.
## config.ini
### General Section
*month* (int) ... Number of the month which should be covered ex. 3 eq. march
*2022* (int) ... Year
*country_cc* (string) ... Country code for your country. Used for holiday determination ex. DE eq. Germany. For  more infos check [https://pypi.org/project/holidays/](here).
*subdivision* (string) ... Subdivision of your country. For  more infos check [https://pypi.org/project/holidays/](here).
*max_consec_shifts* (int) ... max shifts/days an employee can take before a free days gets forced.
*overtime_modifier* (float (0,1)) ... the algorithm trys to balance the overtime of each employee for the current month entirely. If the overtime between the employees differs too much, consider lowering this value for a softer balancing. Value should be between 0 and 1 (represents percantage).
*force_pref_free* (bool) ... Each employee can mark preferred free days. The algorithm trys to maximize those days for each employee. Nevertheless this value forces the algorithm to fulfill all preferred free days. 
*nightshift_last_month* (string (employee)) ... As every day is covered and every day contains a nightshift, the first day of the month has a trailing night shift by this Employee.

### Contraint Section
*one_empl_per_period* (bool) ... Only one employee per shift.
*one_shift_per_day* (bool) ... Each employee can only cover one shift per day.
*free_weekend* (bool) ... Each employee needs to have a free weekend.
*not_two_consec_nights* (bool) ... Each employee should not work two consecutive nights.
*respect_worktime* (bool) ... Each employees max worktime and overtime is respected.
*assure_free_days* (bool) ... Each employee should have at least num of weekend days plus public holidays as free days.
*respect_following_employee* (bool) ... An employee may have an employee which should not replace its consecutive shift.
*respect_pref_free* (bool) ... Maximize the preferred free days of each employee.
*respect_no_single_dayshift* (bool) ... Employees may have the constraint to not perform a single days shift.
*max_n_days_consec_shifts* (bool) ... Employee should only work for max *max_consec_shifts* consecutive days/shifts.
*max_two_consec_dayshifts* (bool) ... Each employee should only work max two consecutive day shifts.

### Shift_worktimes Section
*dayshifthours* (float) ... workhours of a dayshift (ex. 3.5).
*nightshifthoursweekend* (float) ... workhours of a 'wn' shift.
*nightshifthoursnotweekend* (float) ... workhours of a 'n' shift.
*nightshifthoursnotweekendhwk* (float) ... workhours of a 'nhwk' shift.
*nightShiftHoursNotWeekendWithD* (float) ... workhours of a 'nhwk' or 'n' shift with following 'd' shift.
*nightShiftHoursWeekendWithD* (float) ... workhours of a 'wn' shift with following 'd' shift.
*team_meeting_time* (float) ... workhours of a team meeting.

### Other_dates Section
*team_meetings* (day list seperated by ',') ... dates of team meetings for the current month. ex. 11,24
*no_dayshift* (day list seperated by ',') ... dates where no day shift is needed. ex. 11,24
*children_holidays* (day list seperated by ',') ... dates where 'hwk' shifts are replaced by 'n' shifts. ex. 11,24
