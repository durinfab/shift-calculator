"""Example of a simple nurse scheduling problem."""
import sys
from ortools.sat.python import cp_model
import csv
import configparser
import calendar
import datetime
import os
import shutil
import holidays
from collections import defaultdict

vacationFile = "vacation.csv"
employeeFile = "employee.csv"
configFile = "config.ini"

#max workstime per employee in minutes
hardCap = 60*60

month = ""
year = ""
subdivision = ""

#contraints
one_empl_per_period = True
one_shift_per_day = True
free_weekend = True
not_two_consec_nights = True
respect_worktime = True
assure_free_days = True
respect_following_employee = True

def main():
    print('Check configs...')
    checkConfigs()

    # Creates the model.
    model = cp_model.CpModel()

    employee_file = open(employeeFile, newline='')
    workerReader = csv.DictReader(employee_file)
    global workerColumns
    workerColumns = defaultdict(list)

    for row in workerReader:
        for (k,v) in row.items():
            workerColumns[k].append(v)

    vacation_file = open(vacationFile, newline='')
    vacationReader = csv.DictReader(vacation_file)
    global vacationColumns
    vacationColumns = defaultdict(list)

    for row in vacationReader:
        for (k,v) in row.items():
            vacationColumns[k].append(v)

    config = configparser.ConfigParser()
    config.sections()
    with open(configFile) as f:
        config.read_file(f)

    print('Parse config...')
    month = int(config["General"]["month"])
    year = int(config["General"]["year"])
    country_cc = config["General"]["country_cc"]
    subdivision = config["General"]["subdivision"]
    
    one_empl_per_period = config["Constraints"]["one_empl_per_period"]
    one_shift_per_day = config["Constraints"]["one_shift_per_day"]
    free_weekend = config["Constraints"]["free_weekend"]
    not_two_consec_nights = config["Constraints"]["not_two_consec_nights"]
    respect_worktime = config["Constraints"]["respect_worktime"]
    assure_free_days = config["Constraints"]["assure_free_days"]
    respect_following_employee = config["Constraints"]["respect_following_employee"]

    # Creates shift variables.
    # shifts[(n, d, s)]: nurse 'n' works shift 's' on day 'd'.

    shifts = {}
    normalShifts = ["n","d"]
    weekendShifts = ["d","wn"]
    allShifts = ["d", "n","wn"]
    allEmployees = workerColumns['name']
    all_days = range(1, calendar.monthrange(year, month)[1]+1)
    dayShiftHours = int(config["Shift_worktimes"]["dayShiftHours"])
    nightShiftHoursWeekend = int(config["Shift_worktimes"]["nightShiftHoursWeekend"])
    nightShiftHoursNotWeekend = int(config["Shift_worktimes"]["nightShiftHoursNotWeekend"])
    nightShiftHoursNotWeekendHWK = int(config["Shift_worktimes"]["nightShiftHoursNotWeekendHWK"])

    
    worktimes_per_worker = {}

    print('Apply possible shifts...')
    #add all possible results
    #search domain
    for d in all_days:
        date = datetime.date(year, month, d)
        weekday = date.weekday()
        for n in workerColumns['name']:
            worktimes_per_worker[n] = []

            # if employee is not on vacation
            if not onVacation(n,d):
                if weekday != 4 and weekday != 5:
                    for s in normalShifts:
                        if doesShift(n,s):
                            shifts[(n, d, s)] = model.NewBoolVar('shift_%s_%s_%s' % (n, d, s))

                else:
                    for s in weekendShifts:
                        if doesShift(n,s):
                            shifts[(n, d, s)] = model.NewBoolVar('shift_%s_%s_%s' % (n, d, s))
                            
    #all reqired minutes
    reqMinutes = 0

    print('Apply constraints...')

    # Each shift is assigned to exactly one employee in the schedule period.
    if one_empl_per_period:
        for d in all_days:
            date = datetime.date(year, month, d)
            weekday = date.weekday()

            freeEmps = []
            for n in workerColumns['name']:
                if not onVacation(n,d) and doesShift(n,allShifts[0]):
                        freeEmps.append(n)

            can = []
            for b in freeEmps:
                can.append(shifts[(b, d, allShifts[0])])
            model.Add(sum(can) == 1)
            reqMinutes += dayShiftHours
            
            if weekday != 4 and weekday != 5:
                # day and normal night shift
                freeEmps = []
                for n in workerColumns['name']:
                    if not onVacation(n,d) and doesShift(n,allShifts[1]):
                        freeEmps.append(n)
                model.Add(sum(shifts[(a, d, allShifts[1])] for a in freeEmps) == 1)
                if weekday == 1 or weekday == 2 or weekday == 3:
                    reqMinutes += nightShiftHoursNotWeekendHWK
                else:
                    reqMinutes += nightShiftHoursNotWeekend
            else:
                # day and weekend night shift
                freeEmps = []
                for n in workerColumns['name']:
                    if not onVacation(n,d) and doesShift(n,allShifts[2]):
                        freeEmps.append(n)
                model.Add(sum(shifts[(a, d, allShifts[2])] for a in freeEmps) == 1)
                reqMinutes += nightShiftHoursWeekend

    if respect_following_employee:
        for n in allEmployees:
            for m in allEmployees:
                if shouldNotRelief(n, m):
                    for d in all_days:
                        if (n,d,'d') in shifts and (m,d,'n') in shifts:
                            model.Add(shifts[(m,d,'n')] == 0).OnlyEnforceIf(shifts[(n,d,'d')])

                        if (n,d,'d') in shifts and (m,d,'wn') in shifts:
                            model.Add(shifts[(m,d,'wn')] == 0).OnlyEnforceIf(shifts[(n,d,'d')])

                        if (n,d,'wn') in shifts and (m,d+1,'d') in shifts:
                            model.Add(shifts[(m,d+1,'d')] == 0).OnlyEnforceIf(shifts[(n,d,'wn')])

                        if (n,d,'n') in shifts and (m,d+1,'d') in shifts:
                            model.Add(shifts[(m,d+1,'d')] == 0).OnlyEnforceIf(shifts[(n,d,'n')])
            
    if one_shift_per_day:
        #only one shift per day
        for n in allEmployees:
            for d in all_days:
                availShifts = []
                for s in allShifts:
                    if (n,d,s) in shifts:
                            availShifts.append(shifts[(n,d,s)])
                model.Add(sum(availShifts) <= 1)

    all_weekends = []
    if free_weekend:
        #free weekend for each employee
        for n in allEmployees:
            collectedWeekends = []
            for d in all_days:
                date = datetime.date(year, month, d)
                weekday = date.weekday()
                if weekday == 4:

                    # if friday
                    i = model.NewBoolVar('%s has free weekend starting at %s' % (n, d))
                    freeWeekend = []
                    good = True
                    if (n,d,'wn') in shifts:
                        freeWeekend.append(shifts[(n,d,'wn')])
                    elif doesShift(n, 'wn'):
                        good = False

                    if (n,d+1,'d') in shifts:
                        freeWeekend.append(shifts[(n,d+1,'d')])
                    elif doesShift(n, 'd'):
                        good = False

                    if (n,d+1,'wn') in shifts:
                        freeWeekend.append(shifts[(n,d+1,'wn')])
                    elif doesShift(n, 'wn'):
                        good = False

                    if (n,d+2,'d') in shifts:
                        freeWeekend.append(shifts[(n,d+2,'d')])
                    elif doesShift(n, 'd'):
                        good = False

                    if (n,d+2,'n') in shifts:
                        freeWeekend.append(shifts[(n,d+2,'n')])
                    elif doesShift(n, 'n'):
                        good = False
                    
                    if good:
                        model.Add(sum(freeWeekend) == 0).OnlyEnforceIf(i)
                        collectedWeekends.append(i)
                        all_weekends.append(i)
            model.Add(sum(collectedWeekends) >= 1)

    free_days_count = 0
    if assure_free_days:
        all_holidays = holidays.country_holidays(country_cc, subdiv=subdivision)
        for d in all_days:
            date = datetime.date(year, month, d)
            #check holiday
            if date in all_holidays:
                free_days_count = free_days_count + 1
            #check weekend
            elif date.weekday() == 5 or date.weekday() == 6:
                free_days_count = free_days_count + 1

        all_emp_free_days = []
        for n in allEmployees:
            collected_free_days = []
            for d in all_days:
                # count free days of employee
                if (n,d,'d') in shifts and (n,d,'n') in shifts:
                    i = model.NewBoolVar('%s has day off on %s' % (n, d))
                    model.Add(sum([shifts[(n,d,'d')], shifts[(n,d,'n')]]) == 0).OnlyEnforceIf(i)  
                    collected_free_days.append(i)
                    all_emp_free_days.append(i)

                if (n,d,'d') in shifts and (n,d,'wn') in shifts:
                    i = model.NewBoolVar('%s has day off on %s' % (n, d))
                    model.Add(sum([shifts[(n,d,'d')], shifts[(n,d,'wn')]]) == 0).OnlyEnforceIf(i)  
                    collected_free_days.append(i)
                    all_emp_free_days.append(i)
            model.Add(sum(collected_free_days) >= free_days_count)


    if not_two_consec_nights:
        #not two consecutive nights
        for n in allEmployees:
            a = len(list(all_days))
            for d in range(1,a):
                availShifts = []
                if (n,d,'n') in shifts:
                    if (n,d+1,'n') in shifts:
                        model.Add(sum([shifts[(n,d,'n')], shifts[(n,d+1,'n')]]) <= 1)
                        
                if (n,d,'n') in shifts:
                    if (n,d+1,'wn') in shifts:
                        model.Add(sum([shifts[(n,d,'n')], shifts[(n,d+1,'wn')]]) <= 1)
                        
                if (n,d,'wn') in shifts:
                    if (n,d+1,'n') in shifts:
                        model.Add(sum([shifts[(n,d,'wn')], shifts[(n,d+1,'n')]]) <= 1)
                        
                if (n,d,'wn') in shifts:
                    if (n,d+1,'wn') in shifts:
                        model.Add(sum([shifts[(n,d,'wn')], shifts[(n,d+1,'wn')]]) <= 1)
                    


    #the min work which needs to be done for each employee
    min_minutes_per_employee = reqMinutes // len(workerColumns['name'])

    # the max work which all employees can fulfill
    max_work = 0

    hours_per_week = workerColumns['hours_per_week']
    overtime_per_employee = workerColumns['overtime']

    deviation = {}
    diff = {}

    if respect_worktime:
        for n in workerColumns['name']:

            # calculate avg worktime per day
            avg = int(hours_per_week[workerColumns['name'].index(n)]) // 7

            # add all vacations worktime
            for e in list(all_days):
                if onVacation(n,e):
                     worktimes_per_worker[n].append(avg)

            #set worktime constraints
            #short night shift not weekend
            tmpDays = [int]
            for e in list(all_days):
                date = datetime.date(year, month, e)
                weekday = date.weekday()
                if weekday == 1 or weekday == 2 or weekday == 3:
                    tmpDays.append(e)
            for d in tmpDays:
                if (n, d, 'n') in shifts:
                    ab = model.NewIntVar(0, nightShiftHoursNotWeekendHWK, "int%s%in" % (n,d))
                    model.Add(ab == nightShiftHoursNotWeekendHWK).OnlyEnforceIf(shifts[(n, d, 'n')])
                    model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'n')].Not())
                    worktimes_per_worker[n].append(ab)

            #long night shift not weekend
            tmpDays = [int]
            for e in list(all_days):
                date = datetime.date(year, month, e)
                weekday = date.weekday()
                if weekday == 0 or weekday == 6:
                    tmpDays.append(e)
            for d in tmpDays:
                if (n, d, 'n') in shifts:
                    ab = model.NewIntVar(0, nightShiftHoursNotWeekend, "int%s%ind" % (n,d))
                    model.Add(ab == nightShiftHoursNotWeekend).OnlyEnforceIf(shifts[(n, d, 'n')])
                    model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'n')].Not())
                    worktimes_per_worker[n].append(ab)
                
            #day shift every day
            for d in all_days:
                if (n, d, 'd') in shifts:
                    ab = model.NewIntVar(0, dayShiftHours, "int%s%id" % (n,d))
                    model.Add(ab == dayShiftHours).OnlyEnforceIf(shifts[(n, d, 'd')])
                    model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'd')].Not())
                    worktimes_per_worker[n].append(ab)

            tmpDays = [int]
            for e in list(all_days):
                date = datetime.date(year, month, e)
                weekday = date.weekday()
                if weekday == 4 or weekday == 5:
                    tmpDays.append(e)
            for d in tmpDays:
                if (n, d, 'wn') in shifts:
                    ab = model.NewIntVar(0, nightShiftHoursWeekend, "int%s%iwn" % (n,d))
                    model.Add(ab == nightShiftHoursWeekend).OnlyEnforceIf(shifts[(n, d, 'wn')])
                    model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'wn')].Not())
                    worktimes_per_worker[n].append(ab)

            #min worktime
            minworktime = min(min_minutes_per_employee, int(hours_per_week[workerColumns['name'].index(n)])*60)
            maxworktime = (int(hours_per_week[workerColumns['name'].index(n)]) // 7) * len(all_days) * 60

            #add overtime
            ot = int(overtime_per_employee[workerColumns['name'].index(n)]) * 60
            
            # work with deviation
            # https://stackoverflow.com/questions/69498730/google-or-tools-employee-scheduling-minimze-the-deviation-between-how-many-ho
            maxDev = (maxworktime - ot) * (maxworktime - ot)
            deviation[n] = model.NewIntVar(-1000000, maxDev, "Deviation_for_employee_%s" % (n))
            diff[n] = model.NewIntVar(-maxDev, maxDev,"Diff_for_employee_%s" % (n))
            model.Add(diff[n] == sum(worktimes_per_worker[n]) - maxworktime + ot)
            
            minusDiff = model.NewIntVar(-maxDev, maxDev,"minusDiff_for_employee_%s" % (n))
            model.Add(minusDiff == -diff[n])
            operands = [diff[n], minusDiff]
            model.AddMaxEquality(deviation[n], operands)

            max_work += maxworktime

    objective = model.NewIntVar(0, len(allEmployees) * hardCap, "Objective")
    model.AddMaxEquality(objective, deviation.values())

    model.Minimize(objective)

    # some checks that should avoid wrong calculation
    if max_work < reqMinutes:
        print('Warning: The current employee setup cannot fulfill the worktime requirements. They will work overtime.')
        # sys.exit()

    # Creates the solver and solve.
    solver = cp_model.CpSolver()
    print('Start solving...')
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL:
        print('Solution:')
        for d in all_days:
            date = datetime.date(year, month, d)
            print('Day %i %s' % (d, calendar.day_name[date.weekday()]))
            for n in allEmployees:
                for s in allShifts:
                    if (n, d, s) in shifts:
                        if solver.Value(shifts[(n, d, s)]) == 1:
                            print('  Employee %s works shift %s' % (n, s))
        print('')
        print('Worktime:')
        all_worktime = 0
        for n in allEmployees:
            minutes = solver.Value(sum(worktimes_per_worker[n]))
            all_worktime += minutes
            print('  Employee %s works %i minutes' % (n, minutes))

        print('')
        print('New Overtime:')
        for n in allEmployees:
            ot = int(overtime_per_employee[workerColumns['name'].index(n)])
            minutes = solver.Value(sum(worktimes_per_worker[n]))
            newOvertime = ((minutes - ((int(hours_per_week[workerColumns['name'].index(n)]) // 7) * len(all_days) * 60)) / 60) + ot
            print('  Employee %s has now a overtime of %d hours' % (n, newOvertime))

        print('')
        print('free weekends:')
        for n in all_weekends:
            val = solver.Value(n)
            if val == 1:
                print('weekend free %s' % (n))
        print('')
        print('free days:')
        for n in range(len(all_emp_free_days)):
            a = solver.Value(all_emp_free_days[n])
            if a == True:
                print(all_emp_free_days[n])
    else:
        print('No optimal solution found !')

    # Statistics.
    print('\nStatistics')
    print('  - conflicts      : %i' % solver.NumConflicts())
    print('  - branches       : %i' % solver.NumBranches())
    print('  - wall time      : %f s' % solver.WallTime())
    print('')
    print("Shift calculator by Fabian During")
    print('')
    print("Press enter to close")
    input()

def checkConfigs():
    createdConfigs = False
    try:
        f = open(employeeFile)
    except IOError:
        with open(employeeFile, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            writer.writerow(["name","hours_per_week","overtime","available_for_shift","not_relief"])
            writer.writerow(["Paula",20,10,"d,wn",])
            writer.writerow(["James",30,5,"n,d,wn",])
            writer.writerow(["Torsten",60,15,"n,d,wn",])
            writer.writerow(["Thira",40,0,"n,d,wn",])
            writer.writerow(["Frank",40,5,"n,d,wn",])

        createdConfigs = True

    # if no global config: generate on
    try:
        config = configparser.ConfigParser()
        config.sections()
        with open(configFile) as f:
            config.read_file(f)
    except IOError:
        config = configparser.RawConfigParser()
        config.add_section('General')
        config.add_section('Constraints')
        config.add_section('Shift_worktimes')
        config.set('General', 'month', '3')
        config.set('General', 'year', '2022')
        config.set('General', 'country_cc', 'DE')
        config.set('General', 'subdivision', 'BB')

        config.set('Constraints', 'one_empl_per_period', 'True')
        config.set('Constraints', 'one_shift_per_day', 'True')
        config.set('Constraints', 'free_weekend', 'True')
        config.set('Constraints', 'not_two_consec_nights', 'True')
        config.set('Constraints', 'respect_worktime', 'True')
        config.set('Constraints', 'assure_free_days', 'True')
        config.set('Constraints', 'respect_following_employee', 'True')

        config.set('Shift_worktimes', 'dayShiftHours', '360')
        config.set('Shift_worktimes', 'nightShiftHoursWeekend', '1050')
        config.set('Shift_worktimes', 'nightShiftHoursNotWeekend', '1095')
        config.set('Shift_worktimes', 'nightShiftHoursNotWeekendHWK', '855')

        with open(configFile, 'w') as configfile:
            config.write(configfile)
        createdConfigs = True

    try:
        f = open(vacationFile)
    except IOError:
        with open(vacationFile, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            writer.writerow(["employee",1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31])
            writer.writerow(["Paula","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])
            writer.writerow(["Torsten","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])
            writer.writerow(["James","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])
            writer.writerow(["Thira","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])
            writer.writerow(["Frank","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])

        createdConfigs = True

    if createdConfigs:
        print("template files created")
        print("consider to change them")
        sys.exit()

def onVacation(name, day):
    i = vacationColumns['employee'].index(name)
    return  vacationColumns[str(day)][i] == "yes"

def doesShift(name, shift):
    i = workerColumns['name'].index(name)
    availShifts = workerColumns['available_for_shift'][i]
    avshifts = availShifts.split(',')
    return shift in avshifts

def shouldNotRelief(empl, next):
    i = workerColumns['name'].index(empl)
    relief = workerColumns['not_relief'][i]
    if relief:
        avshifts = relief.split(',')
        return next in avshifts
    return False

if __name__ == '__main__':
    main()