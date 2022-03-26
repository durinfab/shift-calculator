"""Example of a simple nurse scheduling problem."""
import subprocess
import sys
from turtle import color
from ortools.sat.python import cp_model
import csv
import configparser
import numpy as np
import pandas as pd
import calendar
import datetime
import holidays
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from collections import defaultdict

vacationFile = "vacation.csv"
employeeFile = "employee.csv"
prefFreeFile = "prefFree.csv"
configFile = "config.ini"

#max workstime per employee in minutes
hardCap = 40*40

month = ""
year = ""
subdivision = ""

#contraints
one_empl_per_period = True
one_shift_per_day = False
free_weekend = False
respect_no_single_dayshift = False
not_two_consec_nights = False
respect_worktime = False
assure_free_days = False
respect_following_employee = False
max_n_days_consec_shifts = False
#no_d_on_hwk = True
respect_pref_free = False
max_two_consec_dayshifts = False
force_pref_free = False

max_consec_shifts = 5

forced_shift_entries = []

nightshift_last_month = ""

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

    prefFree_file = open(prefFreeFile, newline='')
    prefFreeReader = csv.DictReader(prefFree_file)

    vacation_file = open(vacationFile, newline='')
    vacationReader = csv.DictReader(vacation_file)

    global prefFreeColumns
    prefFreeColumns = defaultdict(list)

    global vacationColumns
    vacationColumns = defaultdict(list)

    for row in prefFreeReader:
        for (k,v) in row.items():
            prefFreeColumns[k].append(v)

    for row in vacationReader:
        for (k,v) in row.items():
            vacationColumns[k].append(v)

    config = configparser.ConfigParser()
    config.sections()
    with open(configFile) as f:
        config.read_file(f)

    print('Parse config...')

    global month
    month = int(config["General"]["month"])

    global year
    year = int(config["General"]["year"])

    country_cc = config["General"]["country_cc"]
    subdivision = config["General"]["subdivision"]
    max_consec_shifts =  int(config["General"]["max_consec_shifts"]) + 1
    overtime_modifier = float(config["General"]["overtime_modifier"])
    
    one_empl_per_period = config["Constraints"]["one_empl_per_period"] == 'True'
    one_shift_per_day = config["Constraints"]["one_shift_per_day"]  == 'True'
    free_weekend = config["Constraints"]["free_weekend"]  == 'True'
    not_two_consec_nights = config["Constraints"]["not_two_consec_nights"]  == 'True'
    respect_worktime = config["Constraints"]["respect_worktime"]  == 'True'
    assure_free_days = config["Constraints"]["assure_free_days"]  == 'True'
    respect_following_employee = config["Constraints"]["respect_following_employee"]  == 'True'
    respect_no_single_dayshift = config["Constraints"]["respect_no_single_dayshift"]  == 'True'
    max_n_days_consec_shifts = config["Constraints"]["max_n_days_consec_shifts"]  == 'True'
    respect_pref_free = config["Constraints"]["respect_pref_free"]  == 'True'
    max_two_consec_dayshifts = config["Constraints"]["max_two_consec_dayshifts"]  == 'True'
    force_pref_free = config["General"]["force_pref_free"]  == 'True'
    
    global nightshift_last_month
    nightshift_last_month = config["General"]["nightshift_last_month"]

    ttt = config["Other_dates"]["team_meetings"]
    team_meetings = ttt.split(',')

    ttt2 = config["Other_dates"]["no_dayshift"]
    no_dayshift = ttt2.split(',')

    ttt3 = config["Other_dates"]["children_holidays"]
    children_holidays = ttt3.split(',')

    ttt4 = config["Other_dates"]["forced_shifts"]
    global forced_shift_entries
    forced_shift_entries = ttt4.split('/')

    shifts = {}
    allShifts = ['d', 'n','wn', 'nhwk']
    allEmployees = workerColumns['name']
    all_days = range(1, calendar.monthrange(year, month)[1]+1)
    dayShiftHours = int(float(config["Shift_worktimes"]["dayShiftHours"]) * 60)
    nightShiftHoursWeekend = int(float(config["Shift_worktimes"]["nightShiftHoursWeekend"]) * 60)
    nightShiftHoursNotWeekend = int(float(config["Shift_worktimes"]["nightShiftHoursNotWeekend"]) * 60)
    nightShiftHoursNotWeekendHWK = int(float(config["Shift_worktimes"]["nightShiftHoursNotWeekendHWK"]) * 60)
    nightShiftHoursNotWeekendWithD = int(float(config["Shift_worktimes"]["nightShiftHoursNotWeekendWithD"]) * 60)
    team_meeting_time = int(float(config["Shift_worktimes"]["team_meeting_time"]) * 60)
    nightShiftHoursWeekendWithD = int(float(config["Shift_worktimes"]["nightShiftHoursWeekendWithD"]) * 60)

    worktimes_per_worker = {}
    worktimes_per_worker_week = {}

    #weekend_days = 0
    #for d in all_days:
    #    date = datetime.date(year, month, d)
    #    weekday = date.weekday()
    #    if weekday == 5 or weekday == 6:
    #        weekend_days = weekend_days + 1

    print('Apply possible shifts...')
    #add all possible results
    #search domain
    for d in all_days:
        date = datetime.date(year, month, d)
        weekday = date.weekday()
        for n in workerColumns['name']:
            worktimes_per_worker[n] = []
            worktimes_per_worker_week[n] = []

            # if employee is not on vacation
            if not onVacation(n,d):
                if doesShift(n,'d') and not str(d) in no_dayshift:
                    shifts[(n, d, 'd')] = model.NewBoolVar('shift_%s_%s_%s' % (n, d, 'd'))
                if weekday == 6 or weekday == 0:
                    if doesShift(n,'n') and not onVacation(n,d+1):
                        shifts[(n, d, 'n')] = model.NewBoolVar('shift_%s_%s_%s' % (n, d, 'n'))
                elif weekday == 1 or weekday == 2 or weekday == 3:
                    if doesShift(n,'nhwk') and not onVacation(n,d+1):
                        shifts[(n, d, 'nhwk')] = model.NewBoolVar('shift_%s_%s_%s' % (n, d, 'nhwk'))
                else:
                    if doesShift(n,'wn') and not onVacation(n,d+1):
                        shifts[(n, d, 'wn')] = model.NewBoolVar('shift_%s_%s_%s' % (n, d, 'wn'))
                            
    #all reqired minutes
    reqMinutes = 0

    print('Apply constraints...')

    # Each shift is assigned to exactly one employee in the schedule period.
    if one_empl_per_period:
        for d in all_days:
            date = datetime.date(year, month, d)
            weekday = date.weekday()

            if not str(d) in no_dayshift:
                freeEmps = []
                for n in workerColumns['name']:
                    if not onVacation(n,d) and doesShift(n,allShifts[0]):
                            freeEmps.append(n)

                can = []
                for b in freeEmps:
                    can.append(shifts[(b, d, allShifts[0])])
                model.Add(sum(can) == 1)
                reqMinutes += dayShiftHours
            
            if (weekday == 1 or weekday == 2 or weekday == 3) and not d in children_holidays:
                # day and normal night shift
                freeEmps = []
                for n in workerColumns['name']:
                    if not onVacation(n,d) and doesShift(n,allShifts[3]) and not onVacation(n,d+1):
                        freeEmps.append(n)
                model.Add(sum(shifts[(a, d, allShifts[3])] for a in freeEmps) == 1)
                reqMinutes += nightShiftHoursNotWeekendHWK
            elif weekday == 4 or weekday == 5:
                # day and weekend night shift
                freeEmps = []
                for n in workerColumns['name']:
                    if not onVacation(n,d) and doesShift(n,allShifts[2]) and not onVacation(n,d+1):
                        freeEmps.append(n)
                model.Add(sum(shifts[(a, d, allShifts[2])] for a in freeEmps) == 1)
                reqMinutes += nightShiftHoursWeekend
            else:
                # day and normal night shift
                freeEmps = []
                for n in workerColumns['name']:
                    if not onVacation(n,d) and doesShift(n,allShifts[1]) and not onVacation(n,d+1):
                        freeEmps.append(n)
                model.Add(sum(shifts[(a, d, allShifts[1])] for a in freeEmps) == 1)
                reqMinutes += nightShiftHoursNotWeekend


    #enter forced shifts
    for d in all_days:
        for n in workerColumns['name']:
            for s in allShifts:
                if checkForcedShifts(n,d,s) and (n,d,s) in shifts:
                    model.Add(shifts[(n,d,s)] == 1)

    if respect_following_employee:
        for n in allEmployees:
            for m in allEmployees:
                if shouldNotRelief(n, m):
                    for d in all_days:
                        if (n,d,'d') in shifts and (m,d,'n') in shifts:
                            model.Add(shifts[(m,d,'n')] == 0).OnlyEnforceIf(shifts[(n,d,'d')])

                        if (n,d,'d') in shifts and (m,d,'nhwk') in shifts:
                            model.Add(shifts[(m,d,'nhwk')] == 0).OnlyEnforceIf(shifts[(n,d,'d')])

                        if (n,d,'d') in shifts and (m,d,'wn') in shifts:
                            model.Add(shifts[(m,d,'wn')] == 0).OnlyEnforceIf(shifts[(n,d,'d')])
            
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
                if weekday == 4 and d+2 < len(all_days):

                    # if friday
                    i = model.NewBoolVar('%s has free weekend starting at %s' % (n, d))
                    freeWeekend = []
                    if (n,d,'wn') in shifts:
                        freeWeekend.append(shifts[(n,d,'wn')])

                    if (n,d+1,'d') in shifts:
                        freeWeekend.append(shifts[(n,d+1,'d')])

                    if (n,d+1,'wn') in shifts:
                        freeWeekend.append(shifts[(n,d+1,'wn')])

                    if (n,d+2,'d') in shifts:
                        freeWeekend.append(shifts[(n,d+2,'d')])

                    if (n,d+2,'n') in shifts:
                        freeWeekend.append(shifts[(n,d+2,'n')])

                    model.Add(sum(freeWeekend) == 0).OnlyEnforceIf(i)
                    collectedWeekends.append(i)
                    all_weekends.append(i)
            model.Add(sum(collectedWeekends) >= 1)

    free_days_count = 0
    all_emp_free_days = []
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

        for n in allEmployees:
            prefFrees = []
            collected_free_days = []
            for d in all_days:
                # count free days of employee
                t = False
                tmp = []
                i = model.NewBoolVar('%s has day off on %s' % (n, d))
                if d-1 > 0:
                    t = (n,d-1,'n') in shifts or (n,d-1,'wn') in shifts or (n,d-1,'nhwk') in shifts
                if (n,d,'d') in shifts:
                    tmp.append(shifts[(n,d,'d')])
                if (n,d,'nhwk') in shifts:
                    tmp.append(shifts[(n,d,'nhwk')])
                if (n,d,'n') in shifts:
                    tmp.append(shifts[(n,d,'n')])
                if (n,d,'wn') in shifts:
                    tmp.append(shifts[(n,d,'wn')])
                if t:
                    if (n,d-1,'n') in shifts:
                        tmp.append(shifts[(n,d-1,'n')])
                    elif (n,d-1,'nhwk') in shifts:
                        tmp.append(shifts[(n,d-1,'nhwk')])
                    else:
                        tmp.append(shifts[(n,d-1,'wn')])
                if str(d) in team_meetings and not onVacation(n,d):
                    model.Add(i == 0)

                if d == 1 and nightshift_last_month == n:
                    model.Add(i == 0)
                else:
                    model.Add(sum(tmp) == 0).OnlyEnforceIf(i)
                    if respect_pref_free and hasPrefFree(n,d):
                        prefFrees.append(i)
                collected_free_days.append(i)
                all_emp_free_days.append(i)
            if max_n_days_consec_shifts:
                for bla in collected_free_days:
                    sublist = []
                    b = collected_free_days.index(bla)
                    sublist = collected_free_days[b:b+max_consec_shifts]
                    if len(sublist) == max_consec_shifts:
                        model.Add(sum(sublist) > 0)

            model.Add(sum(collected_free_days) >= free_days_count)
            if respect_pref_free and len(prefFrees) != 0:
                if force_pref_free:
                    model.Add(sum(prefFrees) == len(prefFrees))
                else:
                    model.Maximize(sum(prefFrees))

    if respect_no_single_dayshift:
        for n in workerColumns['name']:
            i = workerColumns['no_single_dayshift'][workerColumns['name'].index(n)]
            if i == 'yes':
                if doesShift(n, 'd'):
                    for d in all_days:
                        if (n,d,'d') in shifts:
                            if d > 1:
                                if (n,d-1,'nhwk') in shifts:
                                    model.Add(shifts[(n,d,'d')] == 0).OnlyEnforceIf(shifts[(n,d-1,'nhwk')].Not())
                                elif (n,d-1,'n') in shifts:
                                    model.Add(shifts[(n,d,'d')] == 0).OnlyEnforceIf(shifts[(n,d-1,'n')].Not())
                                elif (n,d-1,'wn') in shifts:
                                    model.Add(shifts[(n,d,'d')] == 0).OnlyEnforceIf(shifts[(n,d-1,'wn')].Not())
                                elif (n,d,'d') in shifts:
                                    model.Add(shifts[(n,d,'d')] == 0)
                            else:
                                model.Add(shifts[(n,d,'d')] == 0)

    #apply last month night shift constrains
    if nightshift_last_month != "":
        if (nightshift_last_month,1,'n') in shifts:
            model.Add(shifts[(nightshift_last_month,1,'n')] == 0)
        elif (nightshift_last_month,1,'wn') in shifts:
            model.Add(shifts[(nightshift_last_month,1,'wn')] == 0)
        elif (nightshift_last_month,1,'nhwk') in shifts:
            model.Add(shifts[(nightshift_last_month,1,'nhwk')] == 0)

    if not_two_consec_nights:
        #not two consecutive nights
        for n in allEmployees:
            double_shift = doesDoubleShift(n)
            a = len(list(all_days))
            for d in range(1,a):
                availShifts = []
                if (n,d,'n') in shifts:
                    if (n,d+1,'n') in shifts:
                        model.Add(sum([shifts[(n,d,'n')], shifts[(n,d+1,'n')]]) <= 1)

                if (n,d,'n') in shifts:
                    if (n,d+1,'nhwk') in shifts:
                        model.Add(sum([shifts[(n,d,'n')], shifts[(n,d+1,'nhwk')]]) <= 1)
                        
                if (n,d,'n') in shifts:
                    if (n,d+1,'wn') in shifts:
                        model.Add(sum([shifts[(n,d,'n')], shifts[(n,d+1,'wn')]]) <= 1)
                        
                if (n,d,'wn') in shifts:
                    if (n,d+1,'nhwk') in shifts:
                        model.Add(sum([shifts[(n,d,'wn')], shifts[(n,d+1,'nhwk')]]) <= 1)

                if (n,d,'wn') in shifts:
                    if (n,d+1,'n') in shifts:
                        model.Add(sum([shifts[(n,d,'wn')], shifts[(n,d+1,'n')]]) <= 1)
                        
                if (n,d,'wn') in shifts:
                    if (n,d+1,'wn') in shifts:
                        model.Add(sum([shifts[(n,d,'wn')], shifts[(n,d+1,'wn')]]) <= 1)

                if (n,d,'nhwk') in shifts:
                    if (n,d+1,'nhwk') in shifts:
                        model.Add(sum([shifts[(n,d,'nhwk')], shifts[(n,d+1,'nhwk')]]) <= 1)

                if (n,d,'nhwk') in shifts:
                    if (n,d+1,'n') in shifts:
                        model.Add(sum([shifts[(n,d,'nhwk')], shifts[(n,d+1,'n')]]) <= 1)
                        
                if (n,d,'nhwk') in shifts:
                    if (n,d+1,'wn') in shifts:
                        model.Add(sum([shifts[(n,d,'nhwk')], shifts[(n,d+1,'wn')]]) <= 1)
                
                if not double_shift:
                    if (n,d,'n') in shifts:
                        if (n,d+1,'d') in shifts:
                            model.Add(sum([shifts[(n,d,'n')], shifts[(n,d+1,'d')]]) <= 1)
                            
                    if (n,d,'wn') in shifts:
                        if (n,d+1,'d') in shifts:
                            model.Add(sum([shifts[(n,d,'wn')], shifts[(n,d+1,'d')]]) <= 1)

                    if (n,d,'nhwk') in shifts:
                        if (n,d+1,'d') in shifts:
                            model.Add(sum([shifts[(n,d,'nhwk')], shifts[(n,d+1,'d')]]) <= 1)

    #one free day between 36h shifts
    for n in allEmployees:
            double_shift = doesDoubleShift(n)
            a = len(list(all_days))
            for d in range(1,a):
                cons = []
                i = model.NewBoolVar('%s has doubleshift a starting at %s' % (n, d))
                i1 = model.NewBoolVar('%s has doubleshift b starting at %s' % (n, d))
                i2 = model.NewBoolVar('%s has doubleshift c starting at %s' % (n, d))
                if (n,d,'n') in shifts and (n,d+1,'d') in shifts:
                    cons.append(i)
                    model.Add(sum([shifts[(n,d,'n')], shifts[(n,d+1,'d')]]) == 2).OnlyEnforceIf(i)
                if (n,d,'wn') in shifts and (n,d+1,'d') in shifts:
                    cons.append(i1)
                    model.Add(sum([shifts[(n,d,'wn')], shifts[(n,d+1,'d')]]) == 2).OnlyEnforceIf(i1)
                if (n,d,'nhwk') in shifts and (n,d+1,'d') in shifts:
                    cons.append(i2)
                    model.Add(sum([shifts[(n,d,'nhwk')], shifts[(n,d+1,'d')]]) == 2).OnlyEnforceIf(i2)

                i3 = model.NewBoolVar('%s has doubleshift safe starting at %s' % (n, d))
                model.Add(sum(cons) == 1).OnlyEnforceIf(i3)

                if (n,d+2,'n') in shifts and (n,d+2,'d') in shifts:
                    model.Add(sum([shifts[(n,d+2,'n')], shifts[(n,d+2,'d')]]) == 0).OnlyEnforceIf(i3)
                if (n,d+2,'wn') in shifts and (n,d+2,'d') in shifts:
                    model.Add(sum([shifts[(n,d+2,'wn')], shifts[(n,d+2,'d')]]) == 0).OnlyEnforceIf(i3)
                if (n,d+2,'nhwk') in shifts and (n,d+2,'d') in shifts:
                    model.Add(sum([shifts[(n,d+2,'nhwk')], shifts[(n,d+2,'d')]]) == 0).OnlyEnforceIf(i3)

    # the max work which all employees can fulfill
    max_work = 0

    hours_per_week = workerColumns['hours_per_week']
    overtime_per_employee = workerColumns['overtime']

    deviation = {}
    diff = {}

    if respect_worktime:
        for n in workerColumns['name']:

            # calculate avg worktime per day
            avg = int(int(hours_per_week[workerColumns['name'].index(n)]) / 5 * 60)

            # add all vacations worktime
            for e in list(all_days):
                date = datetime.date(year, month, e)
                weekday = date.weekday()
                if onVacation(n,e) and weekday != 6 and weekday != 5:
                    worktimes_per_worker[n].append(avg)

            #apply last month
            if n == nightshift_last_month:
                if isLastMonthShiftN(n,1):
                    worktimes_per_worker[n].append(555) #9,25
                elif isLastMonthShiftWN(n,1):
                    worktimes_per_worker[n].append(315) #5,25
                elif isLastMonthShiftHWK(n,1):
                    worktimes_per_worker[n].append(510) #8,5 

            #apply last month
            ab1 = model.NewIntVar(-1000, 1, "lastmonth%s%i" % (n,d))
            i = len(all_days)
            if (n, len(all_days), 'n') in shifts:
                model.Add(ab1 == -555).OnlyEnforceIf(shifts[(n, len(all_days), 'n')])
                model.Add(ab1 == 0).OnlyEnforceIf(shifts[(n, len(all_days), 'n')].Not())
            elif (n, len(all_days), 'wn') in shifts:
                model.Add(ab1 == -315).OnlyEnforceIf(shifts[(n, len(all_days), 'wn')])
                model.Add(ab1 == 0).OnlyEnforceIf(shifts[(n, len(all_days), 'wn')].Not())
            elif (n, len(all_days), 'nhwk') in shifts:
                model.Add(ab1 == -510).OnlyEnforceIf(shifts[(n, len(all_days), 'nhwk')])
                model.Add(ab1 == 0).OnlyEnforceIf(shifts[(n, len(all_days), 'nhwk')].Not())
                
            worktimes_per_worker[n].append(ab1)

            #apply team meetings
            for d in all_days:
                if not onVacation(n,d) and d in team_meetings:
                    ab = model.NewIntVar(0, team_meeting_time, "tm%s%i" % (n,d))
                    if (n, d-1, 'n') in shifts:
                        model.Add(ab == team_meeting_time).OnlyEnforceIf(shifts[(n, d-1, 'n')].Not())
                    elif (n, d-1, 'wn') in shifts:
                        model.Add(ab == team_meeting_time).OnlyEnforceIf(shifts[(n, d-1, 'wn')].Not())
                    elif (n, d-1, 'nhwk') in shifts:
                        model.Add(ab == team_meeting_time).OnlyEnforceIf(shifts[(n, d-1, 'nhwk')].Not())

                    if (n, d-1, 'n') in shifts:
                        model.Add(ab == team_meeting_time - 30).OnlyEnforceIf(shifts[(n, d-1, 'n')])
                    elif (n, d-1, 'wn') in shifts:
                        model.Add(ab == team_meeting_time - 30).OnlyEnforceIf(shifts[(n, d-1, 'wn')].Not())
                    elif (n, d-1, 'nhwk') in shifts:
                        model.Add(ab == team_meeting_time).OnlyEnforceIf(shifts[(n, d-1, 'nhwk')].Not())
                    worktimes_per_worker[n].append(ab)


            #set worktime constraints
            #short night shift not weekend
            tmpDays = [int]
            for e in list(all_days):
                date = datetime.date(year, month, e)
                weekday = date.weekday()
                if weekday == 1 or weekday == 2 or weekday == 3:
                    tmpDays.append(e)
            for d in tmpDays:
                if (n, d, 'nhwk') in shifts:
                    ab = model.NewIntVar(0, nightShiftHoursNotWeekendWithD, "int%s%in" % (n,d))

                    if (n, d+1, 'd') in shifts:
                        kn = model.NewBoolVar("boolfollowd%s%in" % (n,d))
                        kn1 = model.NewBoolVar("boolnotfollowd%s%in" % (n,d))
                        kn2 = model.NewBoolVar("boolnotsfollowd%s%in" % (n,d))
                        kn3 = model.NewBoolVar("boolnotdsfollowd%s%in" % (n,d))

                        model.AddBoolXOr([kn, kn1, kn2, kn3])

                        model.Add(sum([shifts[(n, d, 'nhwk')], shifts[(n, d+1, 'd')]]) == 2).OnlyEnforceIf(kn)
                        model.Add(sum([shifts[(n, d, 'nhwk')], shifts[(n, d+1, 'd')].Not()]) == 2).OnlyEnforceIf(kn1)
                        model.Add(sum([shifts[(n, d, 'nhwk')].Not(), shifts[(n, d+1, 'd')].Not()]) == 2).OnlyEnforceIf(kn2)
                        model.Add(sum([shifts[(n, d, 'nhwk')].Not(), shifts[(n, d+1, 'd')]]) == 2).OnlyEnforceIf(kn3)

                        model.Add(ab == nightShiftHoursNotWeekendHWK).OnlyEnforceIf(kn1)
                        if d+1 in team_meetings:
                            model.Add(ab == 60).OnlyEnforceIf(kn)
                        else:
                            model.Add(ab == nightShiftHoursNotWeekendWithD).OnlyEnforceIf(kn)
                        
                        model.Add(ab == 0).OnlyEnforceIf(kn2)
                        model.Add(ab == 0).OnlyEnforceIf(kn3)
                    else:
                        model.Add(ab == nightShiftHoursNotWeekendHWK).OnlyEnforceIf(shifts[(n, d, 'nhwk')])
                    model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'nhwk')].Not())
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

                    if (n, d+1, 'd') in shifts:
                        kn = model.NewBoolVar("nboolfollowd%s%in" % (n,d))
                        kn1 = model.NewBoolVar("nboolnotfollowd%s%in" % (n,d))
                        kn2 = model.NewBoolVar("nboolnotsfollowd%s%in" % (n,d))
                        kn3 = model.NewBoolVar("nboolnotdsfollowd%s%in" % (n,d))

                        model.AddBoolXOr([kn, kn1, kn2, kn3])

                        model.Add(sum([shifts[(n, d, 'n')], shifts[(n, d+1, 'd')]]) == 2).OnlyEnforceIf(kn)
                        model.Add(sum([shifts[(n, d, 'n')], shifts[(n, d+1, 'd')].Not()]) == 2).OnlyEnforceIf(kn1)
                        model.Add(sum([shifts[(n, d, 'n')].Not(), shifts[(n, d+1, 'd')].Not()]) == 2).OnlyEnforceIf(kn2)
                        model.Add(sum([shifts[(n, d, 'n')].Not(), shifts[(n, d+1, 'd')]]) == 2).OnlyEnforceIf(kn3)

                        model.Add(ab == nightShiftHoursNotWeekend).OnlyEnforceIf(kn1)
                        if d+1 in team_meetings:
                            model.Add(ab == 60).OnlyEnforceIf(kn)
                        else:
                            model.Add(ab == nightShiftHoursNotWeekendWithD).OnlyEnforceIf(kn)
                        
                        model.Add(ab == 0).OnlyEnforceIf(kn2)
                        model.Add(ab == 0).OnlyEnforceIf(kn3)
                    else:
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

                    if (n, d+1, 'd') in shifts:
                        kn = model.NewBoolVar("wnboolfollowd%s%in" % (n,d))
                        kn1 = model.NewBoolVar("wnboolnotfollowd%s%in" % (n,d))
                        kn2 = model.NewBoolVar("wnboolnotsfollowd%s%in" % (n,d))
                        kn3 = model.NewBoolVar("wnboolnotdsfollowd%s%in" % (n,d))

                        model.AddBoolXOr([kn, kn1, kn2, kn3])

                        model.Add(sum([shifts[(n, d, 'wn')], shifts[(n, d+1, 'd')]]) == 2).OnlyEnforceIf(kn)
                        model.Add(sum([shifts[(n, d, 'wn')], shifts[(n, d+1, 'd')].Not()]) == 2).OnlyEnforceIf(kn1)
                        model.Add(sum([shifts[(n, d, 'wn')].Not(), shifts[(n, d+1, 'd')].Not()]) == 2).OnlyEnforceIf(kn2)
                        model.Add(sum([shifts[(n, d, 'wn')].Not(), shifts[(n, d+1, 'd')]]) == 2).OnlyEnforceIf(kn3)

                        model.Add(ab == nightShiftHoursWeekend).OnlyEnforceIf(kn1)
                        if d+1 in team_meetings:
                            model.Add(ab == 60).OnlyEnforceIf(kn)
                        else:
                            model.Add(ab == nightShiftHoursWeekendWithD).OnlyEnforceIf(kn)
                        
                        model.Add(ab == 0).OnlyEnforceIf(kn2)
                        model.Add(ab == 0).OnlyEnforceIf(kn3)
                    else:
                        model.Add(ab == nightShiftHoursWeekend).OnlyEnforceIf(shifts[(n, d, 'wn')])

                    model.Add(ab == 0).OnlyEnforceIf(shifts[(n, d, 'wn')].Not())
                    worktimes_per_worker[n].append(ab)
                    

            #max worktime
            maxworktime = int((int(hours_per_week[workerColumns['name'].index(n)]) / 5) * (len(all_days) - free_days_count) * 60)

            print("%s should work %i minutes per month" % (n, maxworktime))

            #add overtime
            ot = int(overtime_per_employee[workerColumns['name'].index(n)]) * 60
            
            # work with deviation
            # https://stackoverflow.com/questions/69498730/google-or-tools-employee-scheduling-minimze-the-deviation-between-how-many-ho
            maxDev = (maxworktime) * (maxworktime)
            deviation[n] = model.NewIntVar(-1000000, maxDev, "Deviation_for_employee_%s" % (n))
            diff[n] = model.NewIntVar(-maxDev, maxDev,"Diff_for_employee_%s" % (n))

            ot = int(ot * overtime_modifier)
            model.Add(diff[n] == sum(worktimes_per_worker[n]) - maxworktime + ot)
            
            minusDiff = model.NewIntVar(-maxDev, maxDev,"minusDiff_for_employee_%s" % (n))
            model.Add(minusDiff == -diff[n])
            operands = [diff[n], minusDiff]
            model.AddMaxEquality(deviation[n], operands)

            max_work += maxworktime

        objective = model.NewIntVar(0, len(allEmployees) * hardCap, "Objective")
        model.AddMaxEquality(objective, deviation.values())

        model.Minimize(objective)

    #minimize single dayshifts
    if False:
        for n in allEmployees:
            if doesShift(n, 'd'):
                tmpbla = []
                for d in all_days:
                    if (n,d,'d') in shifts:
                        tmpbla.append(shifts[(n,d,'d')])
                if len(tmpbla) != 0:
                    model.Add(sum(tmpbla) <= 6)

    if max_two_consec_dayshifts:
        for n in allEmployees:
            a = len(list(all_days))
            for d in range(1,a,2):
                if (n,d,'d') in shifts:
                    if (n,d+1,'d') in shifts:
                        model.Add(sum([shifts[(n,d,'d')], shifts[(n,d+1,'d')]]) <= 1)

    # some checks that should avoid wrong calculation
    if max_work < reqMinutes:
        print('Warning: The current employee setup cannot fulfill the worktime requirements. They will work overtime.')
        # sys.exit()

    # Creates the solver and solve.
    solver = cp_model.CpSolver()
    print('Start solving...')
    status = solver.Solve(model)

    if status == cp_model.FEASIBLE:
        print("A solution was found, but we don't know if it's optimal...")

    if status == cp_model.OPTIMAL:

        # create panda dataframe
        d = pd.to_datetime(f'{calendar.month_name[month]} {year}', format='%B %Y')
        dates = pd.date_range(start = d, periods = d.daysinmonth)
        df = pd.DataFrame(index=dates, columns=allEmployees)

        ind = ["overtime", "actual worktime"]
        odf = pd.DataFrame(index=ind, columns=allEmployees)


        print('Solution:')
        
        for d in all_days:
            date = datetime.date(year, month, d)
            print('Day %i %s' % (d, calendar.day_name[date.weekday()]))

            pre_day = False
            if d-1 > 1:
                pre_day = True

            is_tm = False
            if str(d) in team_meetings:
                is_tm = True
            for n in allEmployees:
                date = datetime.date(year, month, d)
                currentDay = date.strftime("%Y-%m-%d")

                end = ""
                if is_tm == True and not onVacation(n,d):
                    end += "TM "
            
                for s in allShifts:

                    if (n, d, s) in shifts:
                        if solver.Value(shifts[(n, d, s)]) == 1:
                            print('  Employee %s works shift %s' % (n, s))
                            
                            if d+1 < len(list(all_days)):
                                date = datetime.date(year, month, d+1)

                            if s == "d":
                                if pre_day or isLastMonthShiftN(n,d) or isLastMonthShiftWN(n,d) or isLastMonthShiftHWK(n,d):
                                    if ((n, d-1, "n") in shifts and solver.Value(shifts[(n, d-1, "n")])) == 1 or isLastMonthShiftN(n,d):
                                        end += "05:00-20:00"
                                    elif ((n, d-1, "nhwk") in shifts and solver.Value(shifts[(n, d-1, "nhwk")]) == 1) or isLastMonthShiftHWK(n,d):
                                        end += "05:00-20:00"
                                    elif ((n, d-1, "wn") in shifts and solver.Value(shifts[(n, d-1, "wn")]) == 1) or isLastMonthShiftWN(n,d):
                                        end += "06:00-20:00"
                                    else:
                                        end += "14:00-20:00"
                                else:
                                    end += "14:00-20:00"
                            elif s == "n":
                                end += "13:00-22:00"
                            elif s == "wn":
                                end += "13:00-22:00"
                            elif s == "nhwk":
                                end += "13:00-22:00"

                if (n, d-1, "n") in shifts and ((n, d, "d") in shifts or str(d) in no_dayshift or not doesShift(n, "d")):
                    if solver.Value(shifts[(n, d-1, "n")]) == 1 and (str(d) in no_dayshift or not doesShift(n, "d") or solver.Value(shifts[(n, d, "d")]) == 0):
                        end = end + "05:00-13:30"


                elif (n, d-1, "nhwk") in shifts and ((n, d, "d") in shifts or str(d) in no_dayshift or not doesShift(n, "d")):
                    if solver.Value(shifts[(n, d-1, "nhwk")]) == 1 and (str(d) in no_dayshift or not doesShift(n, "d") or solver.Value(shifts[(n, d, "d")]) == 0):
                        end = end + "05:00-09:00"

                elif (n, d-1, "wn") in shifts and ((n, d, "d") in shifts or str(d) in no_dayshift or not doesShift(n, "d")):
                    if solver.Value(shifts[(n, d-1, "wn")]) == 1 and (str(d) in no_dayshift or not doesShift(n, "d") or solver.Value(shifts[(n, d, "d")]) == 0):
                        end = end + "06:00-13:30"

                elif (end == "" or end == "TM ") and ((isLastMonthShiftN(n,1) or isLastMonthShiftHWK(n,1) or isLastMonthShiftWN(n,1))):
                    if isLastMonthShiftN(n,1):
                        end += "05:00-13:30"
                    elif isLastMonthShiftHWK(n,1):
                        end += "05:00-09:00"
                    elif isLastMonthShiftWN(n,1):
                        end += "06:00-13:30"
                df.xs(currentDay)[n] = end
        print('')
        print('Worktime:')
        all_worktime = 0
        for n in allEmployees:
            minutes = solver.Value(sum(worktimes_per_worker[n]))
            for aaaa in worktimes_per_worker[n]:
                if solver.Value(aaaa) != 0:
                    print(solver.Value(aaaa))
            all_worktime += minutes
            odf.xs("actual worktime")[n] = "%i hours" % (minutes // 60)
            print('  Employee %s works %i from minutes' % (n, minutes))

        print('')
        print('New Overtime:')
        for n in allEmployees:
            ot = int(overtime_per_employee[workerColumns['name'].index(n)])
            minutes = solver.Value(sum(worktimes_per_worker[n]))
            newOvertime = ((minutes - int((int(hours_per_week[workerColumns['name'].index(n)]) / 5) * (len(all_days) - free_days_count) * 60)) / 60) + ot
            odf.xs("overtime")[n] = newOvertime
            print('  Employee %s has now a overtime of %d hours' % (n, newOvertime))

        print('')
        print('free weekends:')
        for n in all_weekends:
            val = solver.Value(n)
            if val == 1:
                print('  weekend free %s' % (n))
        print('')
        print('free days:')
        i = 0
        for n in range(len(all_emp_free_days)):
            a = solver.Value(all_emp_free_days[n])
            if a == True:
                i += 1
                print("  %s" % all_emp_free_days[n])
    else:
        print('No optimal solution found !')
        return

    df = df.fillna('')

    filestr = "shifts-%i-%i.pdf" % (month, year)

    pp = PdfPages(filestr)
    
    fig, ax =plt.subplots(figsize=(12,4))
    #color weekends
    colors = []
    #tmp22 = []
    #for a in range(1,len(allEmployees) + 1):
    #    tmp22.append("#56666")
    #colors.append(tmp22)
    for e in list(all_days):
        date = datetime.date(year, month, e)
        weekday = date.weekday()
        tmpa = []
        if weekday == 5 or weekday == 6:
            #tmpa.append("w")
            for a in range(1,len(allEmployees)+1):
                tmpa.append("#42ff9a")
            colors.append(tmpa)
        else:
            for a in range(1,len(allEmployees)+1):
                tmpa.append("w")
            colors.append(tmpa)



    ax.axis('tight')
    ax.axis('off')
    the_table = ax.table(rowLabels=dates.strftime('%Y-%m-%d %A'), cellText=df.values,colLabels=df.columns,loc='center',cellColours=colors)
    pp.savefig(fig, bbox_inches='tight')
    plt.close()

    fig1, ax1 =plt.subplots(figsize=(12,4))
    ax1.axis('tight')
    ax1.axis('off')
    the_table1 = ax1.table(rowLabels=ind, cellText=odf.values,colLabels=odf.columns,loc='center')
    txt = "required free days %s" % (free_days_count)
    fig1.text(.1,.1,txt)
    pp.savefig(fig1, bbox_inches='tight')
    plt.close()
    pp.close()
    subprocess.Popen([filestr],shell=True)


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
            writer.writerow(["name","hours_per_week","overtime","available_for_shift","not_replaced_by"])
            writer.writerow(["Paula",20,10,"d,wn,nhwk","James"])
            writer.writerow(["James",30,5,"n,d,wn,nhwk",])
            writer.writerow(["Torsten",60,15,"n,d,wn,nhwk",])
            writer.writerow(["Thira",40,0,"n,d,wn,nhwk",])
            writer.writerow(["Frank",40,5,"n,d,wn,nhwk",])

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
        config.set('General', 'max_consec_shifts', '5')
        config.set('General', 'overtime_modifier', '0.5')
        config.set('General', 'force_pref_free', 'True')
        config.set('General', 'nightshift_last_month', 'Enter')

        config.set('Constraints', 'one_empl_per_period', 'True')
        config.set('Constraints', 'one_shift_per_day', 'True')
        config.set('Constraints', 'free_weekend', 'True')
        config.set('Constraints', 'not_two_consec_nights', 'True')
        config.set('Constraints', 'respect_worktime', 'True')
        config.set('Constraints', 'assure_free_days', 'True')
        config.set('Constraints', 'respect_following_employee', 'True')
        config.set('Constraints', 'no_d_on_hwk', 'True')
        config.set('Constraints', 'respect_pref_free', 'True')
        config.set('Constraints', 'respect_no_single_dayshift', 'True')
        config.set('Constraints', 'max_n_days_consec_shifts', 'True')
        config.set('Constraints', ' max_two_consec_dayshifts', 'True')

        config.set('Shift_worktimes', 'dayShiftHours', '36.0')
        config.set('Shift_worktimes', 'nightShiftHoursWeekend', '105.0')
        config.set('Shift_worktimes', 'nightShiftHoursNotWeekend', '109.5')
        config.set('Shift_worktimes', 'nightShiftHoursNotWeekendHWK', '82.5')
        config.set('Shift_worktimes', 'nightShiftHoursNotWeekendWithD', '82.5')
        config.set('Shift_worktimes', 'nightShiftHoursWeekendWithD', '82.5')
        config.set('Shift_worktimes', 'team_meeting_time', '24.0')

        config.set('Other_dates', 'team_meetings', '1,2')
        config.set('Other_dates', 'no_dayshift', '1,2')
        config.set('Other_dates', 'children_holidays', '1,2')

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

    try:
        f = open(prefFreeFile)
    except IOError:
        with open(prefFreeFile, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            writer.writerow(["employee",1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31])
            writer.writerow(["Paula","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])
            writer.writerow(["Torsten","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])
            writer.writerow(["James","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])
            writer.writerow(["Thira","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])
            writer.writerow(["Frank","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no","no"])

        createdConfigs = True

    if createdConfigs:
        print("Template files created...")
        print("Consider to change them!")
        print("Shift calculator by Fabian During")
        print('')
        print("Press enter to close")
        input()
        sys.exit()

def onVacation(name, day):
    i = vacationColumns['employee'].index(name)
    if day-1 < len(vacationColumns):
        return vacationColumns[str(day)][i] == "yes"
    return False

def doesDoubleShift(name):
    i = workerColumns['name'].index(name)
    value = workerColumns['double_shift'][i]
    return value == "yes"

def hasPrefFree(name, day):
    i = prefFreeColumns['employee'].index(name)
    return  prefFreeColumns[str(day)][i] == "yes"

def doesShift(name, shift):
    i = workerColumns['name'].index(name)
    availShifts = workerColumns['available_for_shift'][i]
    avshifts = availShifts.split(',')
    return shift in avshifts

def checkForcedShifts(name, day, shift):
    for i in forced_shift_entries:
        aa = i.split(",")
        if name == aa[0] and str(day) == aa[1] and shift == aa[2]:
            return True
    return False

def isLastMonthShiftN(name,day):

    day = int(day)

    date = datetime.date(year, month, day)
    weekday = date.weekday()

    if weekday - 1 < 0:
        weekday = 6
    else:
        weekday = weekday - 1

    if name == nightshift_last_month and day == 1 and (weekday == 6 or weekday == 0):
        return True
    return False

def isLastMonthShiftHWK(name,day):
     
    day = int(day)
    
    date = datetime.date(year, month, day)
    weekday = date.weekday()
    
    if weekday - 1 < 0:
        weekday = 6
    else:
        weekday = weekday - 1

    if name == nightshift_last_month and day == 1 and (weekday == 1 or weekday == 2 or weekday == 3):
        return True
    return False    

def isLastMonthShiftWN(name,day):

    day = int(day)

    date = datetime.date(year, month, day)
    weekday = date.weekday()

    if weekday - 1 < 0:
        weekday = 6
    else:
        weekday = weekday - 1
    
    if name == nightshift_last_month and day == 1 and (weekday == 4 or weekday == 5):
        return True
    return False      

def shouldNotRelief(empl, next):
    i = workerColumns['name'].index(empl)
    relief = workerColumns['not_replaced_by'][i]
    if relief:
        avshifts = relief.split(',')
        return next in avshifts
    return False

#https://stackoverflow.com/questions/52561643/how-to-step-one-week-7-days-in-a-for-loop-datetime
def daterange(start_date, end_date):
     for n in range(0, int((end_date - start_date).days) + 1, 7):
         yield start_date + datetime.timedelta(n)

if __name__ == '__main__':
    main()