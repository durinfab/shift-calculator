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
    dayShiftHours = 6
    nightShiftHoursWeekend = 17,5
    nightShiftHoursNotWeekend = 18,25

    #add all possible results
    #search domain
    for d in all_days:
        date = datetime.date(now.year, now.month, d)
        weekday = date.weekday()
        for n in workerColumns['name']:

            workerIndex = workerColumns['name'].index(n)

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

    # Each shift is assigned to exactly one employee in the schedule period.
    for d in all_days:
        date = datetime.date(now.year, now.month, d)
        weekday = date.weekday()

        freeEmps = []
        for n in workerColumns['name']:
            if not onVacation(n,d) and doesShift(n,allShifts[0]):
                freeEmps.append(n)
        model.Add(sum(shifts[(a, d, allShifts[0])] for a in freeEmps) == 1)
        
        if weekday != 4 and weekday != 5:
            # day and normal night shift
            freeEmps = []
            for n in workerColumns['name']:
                if not onVacation(n,d) and doesShift(n,allShifts[1]):
                    freeEmps.append(n)
            model.Add(sum(shifts[(a, d, allShifts[1])] for a in freeEmps) == 1)
        else:
            # day and weekend night shift
            freeEmps = []
            for n in workerColumns['name']:
                if not onVacation(n,d) and doesShift(n,allShifts[2]):
                    freeEmps.append(n)
            model.Add(sum(shifts[(a, d, allShifts[2])] for a in freeEmps) == 1)


    # Each nurse works at most one shift per day.
    #for n in all_nurses:
    #    for d in all_days:
    #        model.Add(sum(shifts[(n, d, s)] for s in all_shifts) <= 1)

    # Try to distribute the shifts evenly, so that each nurse works
    # min_shifts_per_nurse shifts. If this is not possible, because the total
    # number of shifts is not divisible by the number of nurses, some nurses will
    # be assigned one more shift.
    #min_shifts_per_nurse = (num_shifts * num_days) // num_nurses
    #if num_shifts * num_days % num_nurses == 0:
    #    max_shifts_per_nurse = min_shifts_per_nurse
    #else:
    #    max_shifts_per_nurse = min_shifts_per_nurse + 1
    #for n in all_nurses:
    #    num_shifts_worked = []
    #    for d in all_days:
    #        for s in all_shifts:
    #            num_shifts_worked.append(shifts[(n, d, s)])
    #    model.Add(min_shifts_per_nurse <= sum(num_shifts_worked))
    #    model.Add(sum(num_shifts_worked) <= max_shifts_per_nurse)

    # Creates the solver and solve.
    solver = cp_model.CpSolver()
    #solver.parameters.linearization_level = 0
    # Enumerate all solutions.
    #solver.parameters.enumerate_all_solutions = True


    class NursesPartialSolutionPrinter(cp_model.CpSolverSolutionCallback):
        """Print intermediate solutions."""

        def __init__(self, shifts, allDays, allShifts, allEmployees, limit):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self._shifts = shifts
            self._allShifts = allShifts
            self._allEmployees = allEmployees
            self._allDays = allDays
            self._solution_count = 0
            self._solution_limit = limit

        def on_solution_callback(self):
            self._solution_count += 1
            print('Solution %i' % self._solution_count)
            for d in self._allDays:
                print('Day %i' % d)
                for n in self._allEmployees:
                    is_working = False
                    for s in self._allShifts:
                        if (n, d, s) in self._shifts:
                            print("lamo %s" % n)
                            print("lamo %s" % d)
                            print("lamo %s" % s)
                            if solver.Value(self._shifts[(n, d, s)]) == 1:
                                is_working = True
                                print('  Employee %s works shift %s' % (n, s))
                    if not is_working:
                        print('  Employee {} does not work'.format(n))
            if self._solution_count >= self._solution_limit:
                print('Stop search after %i solutions' % self._solution_limit)
                self.StopSearch()

        def solution_count(self):
            return self._solution_count

    # Display the first five solutions.
    solution_limit = 5
    solution_printer = NursesPartialSolutionPrinter(shifts,
                                                    all_days, allShifts, allEmployees,
                                                    solution_limit)

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
    i = vacationColumns['workers'].index(name)
    availShifts = workerColumns['available_for_shift'][i]
    avshifts = availShifts.split(',')
    return shift in avshifts

if __name__ == '__main__':
    main()