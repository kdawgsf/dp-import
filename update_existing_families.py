from __future__ import print_function
from collections import defaultdict
import csv
import datetime
import sys

def usage(error=None):
    if error:
        print("ERROR:", error)
    print('''
Usage: python update_existing_families.py <dp-report-221.csv> <district-data.csv>

Creates files to be imported into DP to update data for existing families.
    <dp-report-221.csv> should be the csv output from DP: Reports -> Custom Report Writer -> 221 -> CSV.
    <district-data.csv> is the Excel spreadsheet received from the district, converted to csv.

Outputs (to current working directory):
    01-student-updates.csv: updates to existing students as well as new students. Import first:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names, Addresses, Other Info
    02-donor-updates.csv: updates to existing donors. Import second:
                 TBD
    ''')
    sys.exit(1)

# TODO: Write out new donors
# TODO: Write out family-level updates (address changes etc). These will go to 02-donor-updates.csv.

DP_REPORT_221_HEADERS = ['DONOR_ID', 'STU_LNAME', 'STU_FNAME', 'STU_NUMBER', 'SCHOOL', 'GRADE',
                         'FIRST_NAME', 'LAST_NAME', 'SP_FNAME', 'SP_LNAME',
                         'ADDRESS', 'ADDRESS2', 'ADDRESS3', 'ADDRESS4', 'CITY', 'OTHER_ID', 'OTHER_DATE']

DISTRICT_DATA_HEADERS = ['School', 'SystemID', 'Student Last Name', 'Student First Name', 'street', 'city',
                         'state', 'zip', 'Mailing_Street', 'Mailing_City', 'Mailing_State', 'Mailing_Zip',
                         'home_phone', 'Parent1 Last Name', 'Parent 1 First Name', 'Parent 2 Last Name',
                         'Parent 2 First Name', 'Parent1DayPhone', 'Parent2DayPhone', 'Parent1Email',
                         'Parent2Email', 'Guardian', 'GuardianDayPhone', 'GuardianEmail', 'Guardianship',
                         'Grade', 'entrycode', 'entrydate', 'exitdate', 'Family', 'Student', 'Family_Ident',
                         'enroll_status', 'Comment', 'PTA_BCE_Permit']

def validate_headers(filename, expected, actual):
    expected_set = set(expected)
    actual_set = set(actual)
    missing_list = list(expected_set.difference(actual_set))
    if len(missing_list) > 0:
        print("Missing expected header(s) in %s: %s" % (filename, missing_list))
        sys.exit(1)
    extra_list = list(actual_set.difference(expected_set))
    if len(extra_list) > 0:
        print("Found unexpected header(s) in %s: %s" % (filename, extra_list))
        sys.exit(1)

# Mapping of district school name to dp school code
DISTRICT_SCHOOL_MAPPING = {
    'Burlingame Intermediate School': 'BIS',
    'Franklin Elementary School': 'FRANKLIN',
    'Hoover Elementary School': 'HOOVER',
    'Lincoln Elementary School': 'LINCOLN',
    'McKinley Elementary School': 'MCKINLEY',
    'Roosevelt Elementary School': 'ROOSEVELT',
    'Washington Elementary School': 'WASHINGTON',
}

def district_school_to_dp_school(name):
    return DISTRICT_SCHOOL_MAPPING[name]

def load_csv_file(filename, expected_headers):
    if not filename.endswith('.csv'):
        print("%s must be a csv file" % (filename))
        sys.exit(1)
    res = []
    with open(filename, 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        validate_headers(filename, expected_headers, reader.fieldnames)
        for row in reader:
            res.append(row)
    return res

if len(sys.argv) != 3:
    usage()

dp_report_221_filename = sys.argv[1]
district_data_filename = sys.argv[2]
student_updates_filename = '01-student-updates.csv'

# Load dp data keyed off student number
dp_records_multidict = defaultdict(list)
for row in load_csv_file(dp_report_221_filename, DP_REPORT_221_HEADERS):
    if len(row['STU_NUMBER']) > 0:
        dp_records_multidict[row['STU_NUMBER']].append(row)

# Load district data keyed off student number ("system id" there)
district_records_dict = {}
for row in load_csv_file(district_data_filename, DISTRICT_DATA_HEADERS):
    district_records_dict[row['SystemID']] = row

# Make updates for existing students
dp_import_studentrecords = []
for student_id in dp_records_multidict:
    for dp_record in dp_records_multidict[student_id]:
        studentrecord = dp_record.copy()
        if student_id in district_records_dict:
            # Returning student
            studentrecord['GRADE'] = district_records_dict[student_id]['Grade']
            studentrecord['SCHOOL'] = district_school_to_dp_school(district_records_dict[student_id]['School'])
        elif dp_record['GRADE'] == '8' and dp_record['SCHOOL'] == 'BIS':
            studentrecord['GRADE'] = '9'
            studentrecord['SCHOOL'] = 'ALUM'
        elif dp_record['SCHOOL'] != 'ALUM':
            studentrecord['SCHOOL'] = 'NOBSD'
        if dp_record != studentrecord:
            dp_import_studentrecords.append(studentrecord)

# Build up students for each family
students_by_family_ident = defaultdict(list)
for key in district_records_dict:
    family_ident = district_records_dict[key]['Family_Ident']
    students_by_family_ident[family_ident].append(key)

# Add new students for existing families
for student_id in district_records_dict:
    district_record = district_records_dict[student_id]
    if student_id in dp_records_multidict:
        continue
    donor_ids_encountered = set()
    for sibling_id in students_by_family_ident[district_record['Family_Ident']]:
        if sibling_id in dp_records_multidict:
            for siblingrecord in dp_records_multidict[sibling_id]:
                if siblingrecord['DONOR_ID'] not in donor_ids_encountered:
                    donor_ids_encountered.add(siblingrecord['DONOR_ID'])
                    studentrecord = {
                        'DONOR_ID': siblingrecord['DONOR_ID'],
                        'STU_LNAME': district_record['Student Last Name'],
                        'STU_FNAME': district_record['Student First Name'],
                        'STU_NUMBER': student_id,
                        'SCHOOL': district_school_to_dp_school(district_record['School']),
                        'GRADE': district_record['Grade'],
                        'FIRST_NAME': siblingrecord['FIRST_NAME'],
                        'LAST_NAME': siblingrecord['LAST_NAME'],
                        'SP_FNAME': siblingrecord['SP_FNAME'],
                        'SP_LNAME': siblingrecord['SP_LNAME'],
                        'ADDRESS': siblingrecord['ADDRESS'],
                        'ADDRESS2': siblingrecord['ADDRESS2'],
                        'ADDRESS3': siblingrecord['ADDRESS3'],
                        'ADDRESS4': siblingrecord['ADDRESS4'],
                        'CITY': siblingrecord['CITY'],
                        'OTHER_ID': '',
                        'OTHER_DATE': ''
                    }
                    dp_import_studentrecords.append(studentrecord)
    if len(donor_ids_encountered) == 0:
        print("TODO Create record for new donor / new student %s and add to dp_import_studentrecords" % (student_id))

# Clean up outputdata
outputdata_fieldnames = list(DP_REPORT_221_HEADERS)
outputdata_fieldnames.remove('OTHER_ID')
for studentrecord in dp_import_studentrecords:
    del studentrecord['OTHER_ID']
    if len(studentrecord['OTHER_DATE']) == 0:
        studentrecord['OTHER_DATE'] = datetime.date.today().strftime('%m/%d/%Y')

# Write outputdata
with open(student_updates_filename, 'w') as outputfile:
    writer = csv.DictWriter(outputfile, outputdata_fieldnames)
    writer.writeheader()
    for studentrecord in dp_import_studentrecords:
        writer.writerow(studentrecord)
