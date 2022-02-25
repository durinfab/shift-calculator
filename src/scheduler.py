"""Example of a simple nurse scheduling problem."""
from ortools.sat.python import cp_model
import csv
import configparser
import calendar
import datetime
import os
from collections import defaultdict

header = ['name', 'hours_per_week', 'overtime', 'available_for_shift', 'not relief']
w1 = ['Paula', '40', '12', 'n,d,n+d', '']
w2 = ['Renate', '35', '-5', 'n,d', 'Paula']

vacationFile = "vacation.csv"
workersFile = "workers.csv"
configFile = "config.ini"


def main():

    print("Welcome to the shift calculator!")

    deleteGeneratedFiles()

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
        return


    # Data.
    num_nurses = 4
    num_shifts = 3
    num_days = 3
    all_nurses = range(num_nurses)
    all_shifts = range(num_shifts)
    all_days = range(num_days)

    # Creates the model.
    model = cp_model.CpModel()

    # Creates shift variables.
    # shifts[(n, d, s)]: nurse 'n' works shift 's' on day 'd'.
    shifts = {}
    for n in all_nurses:
        for d in all_days:
            for s in all_shifts:
                shifts[(n, d,
                        s)] = model.NewBoolVar('shift_n%id%is%i' % (n, d, s))

    # Each shift is assigned to exactly one nurse in the schedule period.
    for d in all_days:
        for s in all_shifts:
            model.Add(sum(shifts[(n, d, s)] for n in all_nurses) == 1)

    # Each nurse works at most one shift per day.
    for n in all_nurses:
        for d in all_days:
            model.Add(sum(shifts[(n, d, s)] for s in all_shifts) <= 1)

    # Try to distribute the shifts evenly, so that each nurse works
    # min_shifts_per_nurse shifts. If this is not possible, because the total
    # number of shifts is not divisible by the number of nurses, some nurses will
    # be assigned one more shift.
    min_shifts_per_nurse = (num_shifts * num_days) // num_nurses
    if num_shifts * num_days % num_nurses == 0:
        max_shifts_per_nurse = min_shifts_per_nurse
    else:
        max_shifts_per_nurse = min_shifts_per_nurse + 1
    for n in all_nurses:
        num_shifts_worked = []
        for d in all_days:
            for s in all_shifts:
                num_shifts_worked.append(shifts[(n, d, s)])
        model.Add(min_shifts_per_nurse <= sum(num_shifts_worked))
        model.Add(sum(num_shifts_worked) <= max_shifts_per_nurse)

    # Creates the solver and solve.
    solver = cp_model.CpSolver()
    solver.parameters.linearization_level = 0
    # Enumerate all solutions.
    solver.parameters.enumerate_all_solutions = True


    class NursesPartialSolutionPrinter(cp_model.CpSolverSolutionCallback):
        """Print intermediate solutions."""

        def __init__(self, shifts, num_nurses, num_days, num_shifts, limit):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self._shifts = shifts
            self._num_nurses = num_nurses
            self._num_days = num_days
            self._num_shifts = num_shifts
            self._solution_count = 0
            self._solution_limit = limit

        def on_solution_callback(self):
            self._solution_count += 1
            print('Solution %i' % self._solution_count)
            for d in range(self._num_days):
                print('Day %i' % d)
                for n in range(self._num_nurses):
                    is_working = False
                    for s in range(self._num_shifts):
                        if self.Value(self._shifts[(n, d, s)]):
                            is_working = True
                            print('  Nurse %i works shift %i' % (n, s))
                    if not is_working:
                        print('  Nurse {} does not work'.format(n))
            if self._solution_count >= self._solution_limit:
                print('Stop search after %i solutions' % self._solution_limit)
                self.StopSearch()

        def solution_count(self):
            return self._solution_count

    # Display the first five solutions.
    solution_limit = 5
    solution_printer = NursesPartialSolutionPrinter(shifts, num_nurses,
                                                    num_days, num_shifts,
                                                    solution_limit)

    solver.Solve(model, solution_printer)

    # Statistics.
    print('\nStatistics')
    print('  - conflicts      : %i' % solver.NumConflicts())
    print('  - branches       : %i' % solver.NumBranches())
    print('  - wall time      : %f s' % solver.WallTime())
    print('  - solutions found: %i' % solution_printer.solution_count())

def deleteGeneratedFiles():
    if os.path.exists(vacationFile):
        os.remove(vacationFile)
    if os.path.exists(workersFile):
        os.remove(workersFile)
    if os.path.exists(configFile):
        os.remove(configFile)

if __name__ == '__main__':
    main()