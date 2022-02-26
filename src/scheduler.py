"""Example of a simple nurse scheduling problem."""
import sys
from ortools.sat.python import cp_model
import csv
import configparser
import calendar
import datetime
import os
from collections import defaultdict

header = ['name', 'hours_per_week', 'overtime', 'available_for_shift', 'not relief']
w1 = ['Paula', '40', '12', 'd,n,wn', '']
w2 = ['Renate', '35', '-5', 'd,n', 'Paula']

vacationFile = "vacation.csv"
workersFile = "workers.csv"
configFile = "config.ini"

def main():

    print("Welcome to the shift calculator!")

    #deleteGeneratedFiles()

    checkConfigs()

    # Creates the model.
    model = cp_model.CpModel()

    employee_file = open(workersFile, newline='')
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

    # Creates shift variables.
    # shifts[(n, d, s)]: nurse 'n' works shift 's' on day 'd'.
    now = datetime.datetime.now()

    shifts = {}
    normalShifts = ["n","d"]
    weekendShifts = ["d","wn"]
    allShifts = ["d", "n","wn"]
    allEmployees = workerColumns['name']
    all_days = range(1, calendar.monthrange(now.year, now.month)[1]+1)
    dayShiftHours = 360
    nightShiftHoursWeekend = 1050 #17,5
    nightShiftHoursNotWeekend = 1095 #18,25
    nightShiftHoursNotWeekendHWK = 855 #14,25

    
    worktimes_per_worker = {}

    #add all possible results
    #search domain
    for d in all_days:
        date = datetime.date(now.year, now.month, d)
        weekday = date.weekday()
        for n in workerColumns['name']:

            workerIndex = workerColumns['name'].index(n)
            worktimes_per_worker[n] = []

            #get all available shift-kinds for employee
            availShifts = workerColumns['available_for_shift'][workerIndex]
            avshifts = availShifts.split(',')

            # if employee is not on vacation
            if not onVacation(n,d):
                if weekday != 4 and weekday != 5:
                    for s in normalShifts:
                        if s in avshifts:
                            shifts[(n, d, s)] = model.NewBoolVar('shift_n%sd%ss%s' % (n, d, s))

                else:
                    for s in weekendShifts:
                        if s in avshifts:
                            shifts[(n, d, s)] = model.NewBoolVar('shift_n%sd%ss%s' % (n, d, s))
                            
    #all reqired minutes
    reqMinutes = 0

    # Each shift is assigned to exactly one employee in the schedule period.
    for d in all_days:
        date = datetime.date(now.year, now.month, d)
        weekday = date.weekday()

        freeEmps = []
        for n in workerColumns['name']:
            if not onVacation(n,d) and doesShift(n,allShifts[0]):
                freeEmps.append(n)
        model.Add(sum(shifts[(a, d, allShifts[0])] for a in freeEmps) == 1)
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


    # Each nurse works at most one shift per day.
    #for n in all_nurses:
    #    for d in all_days:
    #        model.Add(sum(shifts[(n, d, s)] for s in all_shifts) <= 1)

    # Try to distribute the shifts evenly, so that each nurse works
    # min_shifts_per_nurse shifts. If this is not possible, because the total
    # number of shifts is not divisible by the number of nurses, some nurses will
    # be assigned one more shift.


    #the min work which needs to be done for each employee
    min_minutes_per_employee = reqMinutes // len(workerColumns['name'])

    # the max work which all employees can fulfill
    max_work = 0

    hours_per_week = workerColumns['hours_per_week']
    for n in workerColumns['name']:

        #set worktime constraints
        #short night shift not weekend
        tmpDays = [int]
        for e in list(all_days):
            date = datetime.date(now.year, now.month, e)
            weekday = date.weekday()
            if ((weekday == 1 or weekday == 2 or weekday == 3) and weekday != 4 and weekday != 5):
                tmpDays.append(e)
        for d in range(len(tmpDays)):
            if (n, d, 'n') in shifts:
                ab = model.NewIntVar(0, nightShiftHoursNotWeekendHWK, "int%s%i" % (n,d))
                model.Add(ab == nightShiftHoursNotWeekendHWK).OnlyEnforceIf(shifts[(n, d, 'n')])
                model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'n')].Not())
                worktimes_per_worker[n].append(ab)

        #long night shift not weekend
        tmpDays = [int]
        for e in list(all_days):
            date = datetime.date(now.year, now.month, e)
            weekday = date.weekday()
            if ((weekday != 1 or weekday != 2 or weekday != 3) and weekday != 4 and weekday != 5):
                tmpDays.append(e)
        for d in tmpDays:
            if (n, d, 'n') in shifts:
                ab = model.NewIntVar(0, nightShiftHoursNotWeekend, "int%s%i" % (n,d))
                model.Add(ab == nightShiftHoursNotWeekend).OnlyEnforceIf(shifts[(n, d, 'n')])
                model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'n')].Not())
                worktimes_per_worker[n].append(ab)
            

        for d in list(all_days):
             if (n, d, 'n') in shifts:
                ab = model.NewIntVar(0, dayShiftHours, "int%s%i" % (n,d))
                model.Add(ab == dayShiftHours).OnlyEnforceIf(shifts[(n, d, 'n')])
                model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'n')].Not())
                worktimes_per_worker[n].append(ab)

        tmpDays = [int]
        for e in list(all_days):
            date = datetime.date(now.year, now.month, e)
            weekday = date.weekday()
            if (weekday == 4 and weekday == 5):
                tmpDays.append(e)
        for d in tmpDays:
            if (n, d, 'n') in shifts:
                ab = model.NewIntVar(0, nightShiftHoursWeekend, "int%s%i" % (n,d))
                model.Add(ab == nightShiftHoursWeekend).OnlyEnforceIf(shifts[(n, d, 'n')])
                model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'n')].Not())
                worktimes_per_worker[n].append(ab)

        #min worktime
        minworktime = min(min_minutes_per_employee, int(hours_per_week[workerColumns['name'].index(n)]))
        maxworktime = (int(hours_per_week[workerColumns['name'].index(n)]) // 7) * len(all_days) * 60

        max_work += maxworktime

        wtn = model.NewIntVar(minworktime, maxworktime, "worktime%s" % n)
        model.Add(sum(worktimes_per_worker[n]) == wtn)

    # some checks that should avoid wrong calculation
    if max_work < reqMinutes:
        print('ERROR: The current worker setup cannot fulfill the requirements!')
        sys.exit()

    # Creates the solver and solve.
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL:
        print('Solution:')
        for d in all_days:
            print('Day %i' % d)
            for n in allEmployees:
                is_working = False
                for s in allShifts:
                    if (n, d, s) in shifts:
                        if solver.Value(shifts[(n, d, s)]) == 1:
                            is_working = True
                            print('  Employee %s works shift %s' % (n, s))
                if not is_working:
                    print('  Employee {} does not work'.format(n))
        print('')
        print('Worktime:')
        for n in allEmployees:
            minutes = solver.Value(sum(worktimes_per_worker[n]))
            print('  Employee %s works %i minutes' % (n, minutes))
    else:
        print('No optimal solution found !')

    # Statistics.
    print('\nStatistics')
    print('  - conflicts      : %i' % solver.NumConflicts())
    print('  - branches       : %i' % solver.NumBranches())
    print('  - wall time      : %f s' % solver.WallTime())

def deleteGeneratedFiles():
    if os.path.exists(vacationFile):
        os.remove(vacationFile)
    if os.path.exists(workersFile):
        os.remove(workersFile)
    if os.path.exists(configFile):
        os.remove(configFile)

def checkConfigs():
    createdConfigs = False
    try:
        f = open(workersFile)
    except IOError:
        #if no workers config: generate one
        with open(workersFile, newline='', mode='w') as employee_file:
            writer = csv.writer(employee_file)

            #generate example data
            writer.writerow(header)
            writer.writerow(w1)
            writer.writerow(w2)

            print("created %s" % workersFile)

            createdConfigs = True

    # if no global config: generate on
    try:
        config = configparser.ConfigParser()
        config.sections()
        with open(configFile) as f:
            config.read_file(f)
    except IOError:
        config = configparser.ConfigParser()
        config.sections()
        with open(configFile, mode='w') as config_file:
            config.add_section('General')
            config.set('General','NotTwoWorkshifts',"True")
            config.set('General','EveryWorkerFreeWeekend', "True")
            config.set('General','WorkerFreeDaysEqualWeekendDaysPlusPublicHolidays', "True")
            config.set('General','BalanceOvertime', "True")
            config.write(config_file)
            config_file.close()

        print("created %s" % configFile)

        createdConfigs = True

    try:
        f = open(vacationFile)
    except IOError:
        #if no month config: generate one
        with open(vacationFile, newline='', mode='w') as month_file:
            writer = csv.writer(month_file)

            now = datetime.datetime.now()
            list1 = ["workers"]
            list1.extend(range(1, calendar.monthrange(now.year, now.month)[1]+1))
            writer.writerow(list1)

            #add workers
            with open(workersFile, newline='') as employee_file:
                reader = csv.DictReader(employee_file)
                columns = defaultdict(list)

                for row in reader:
                    for (k,v) in row.items():
                        columns[k].append(v)
                for workers in columns['name']:
                    writer.writerow([workers])

            print("created %s" % vacationFile)

            createdConfigs = True

    if createdConfigs:
        sys.exit()

def onVacation(name, day):
    i = vacationColumns['workers'].index(name)
    return  vacationColumns[str(day)][i] == "yes"

def doesShift(name, shift):
    i = workerColumns['name'].index(name)
    availShifts = workerColumns['available_for_shift'][i]
    avshifts = availShifts.split(',')
    return shift in avshifts

if __name__ == '__main__':
    main()