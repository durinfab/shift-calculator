# shift-calculator

Using Googles OR-Tools we want to create an automatic shift calculator with the following contraints:

- shifts
    - Monday
        - 13:00 to 13:30 (next day)
        - 14:00 to 20:00
    - Thuesday
        - 13:00 to 9:00 (next day)
        - 14:00 to 20:00
    - Wednesday
        - 13:00 to 9:00 (next day)
        - 14:00 to 20:00
    - Thursday
        - 13:00 to 9:00 (next day)
        - 14:00 to 20:00
    - Friday
        - 13:00 to 13:30 (next day)
        - 14:00 to 20:00
    - Saturday
        - 13:00 to 13:30 (next day)
        - 14:00 to 20:00
            - every second week
    - Sunday
        - 13:00 to 13:30 (next day)
        - 14:00 to 20:00
            - every second week
    - holidays like Mo-Fri
        - except Wednesday, Thursday, Friday
            - 13:00 to 13:30 for all night shifts
- employee conf
    - hours per week
    - count of overtime
    - worker shift combinations
        - night shift
        - day shift
        - night+day shift (36h)
    - vacations
    - some employees should not relief specific workers
- other constraints
    - not two consecutive night shifts
    - every employees should have a free weekend
    - every employees should have count of weekend days + public holidays free days per month
    - try to reduce overtime
- worktime calculation
    - Mo-Thur
        - 22-5 counts as quarter of work time
    - Fri-Sun
        - 22-6 counts as quarter of work time
    - every 6 hours -> 30 min break


- night shift weekend
    6+2,5+2+6+1=17,5h
- night shift not weekend
    6+2,5+1,75+6+2=18,25h
- day shift
    6h

