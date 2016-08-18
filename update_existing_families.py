from __future__ import print_function
from collections import defaultdict
import csv
import datetime
import sys

# Usage: python update_existing_families.py <dp-report-221.csv> <district-data-export.csv> <output.csv>

# TODO: Print usage
# TODO: Validate command-line args
# TODO: Instead of <output.csv>, take output folder so we can dump multiple files there
# TODO: - I see 3 files: 1. Student updates/additions, 2. Donor updates, 3. New donors
# TODO: Write out family-level updates (address changes etc). These will go to a separate file.
# TODO: Don't emit row for existing students who haven't changed grade or school

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

def validate_headers(expected, actual, name):
    expected_set = set(expected)
    actual_set = set(actual)
    missing_list = list(expected_set.difference(actual_set))
    if len(missing_list) > 0:
        print("Missing expected header(s) in %s: %s" % (name, missing_list))
        sys.exit(1)
    extra_list = list(actual_set.difference(expected_set))
    if len(extra_list) > 0:
        print("Found unexpected header(s) in %s: %s" % (name, extra_list))
        sys.exit(1)

# Identify existing families:
# - Update student information particularly if they have changed school.
# - Add any new students to the existing families
# - Update any students who are no longer in BSD (set school="No Longer in BSD").
# - If possible, update the address of existing donor/families if they have moved.
# - If possible, update any email changes. 

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

# Load dp data keyed off student number
dp_records_multidict = defaultdict(list)
with open(sys.argv[1], 'rb') as dp_inputfile:
    reader = csv.DictReader(dp_inputfile)
    validate_headers(DP_REPORT_221_HEADERS, reader.fieldnames, "DonorPerfect export")
    for row in reader:
        if len(row['STU_NUMBER']) > 0:
            dp_records_multidict[row['STU_NUMBER']].append(row)
        
# Load district data keyed off student number ("system id" there)
district_records_dict = {}
with open(sys.argv[2], 'rb') as district_inputfile:
    reader = csv.DictReader(district_inputfile)
    validate_headers(DISTRICT_DATA_HEADERS, reader.fieldnames, "district data")
    for row in reader:
        district_records_dict[row['SystemID']] = row

# Make updates for existing students
dp_import_studentrecords = []
for student_id in dp_records_multidict:
    for dp_record in dp_records_multidict[student_id]:
        if student_id in district_records_dict:
            # Returning student
            studentrecord = dp_record.copy()
            # Update current grade
            studentrecord['GRADE'] = district_records_dict[student_id]['Grade']
            # Update school
            studentrecord['SCHOOL'] = district_school_to_dp_school(district_records_dict[student_id]['School'])
            dp_import_studentrecords.append(studentrecord)
        elif dp_record['GRADE'] == '8' and dp_record['SCHOOL'] == 'BIS':
            # Graduation time
            studentrecord = dp_record.copy()
            studentrecord['GRADE'] = '9'
            studentrecord['SCHOOL'] = 'ALUM'
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
    for sibling_id in students_by_family_ident[district_record['Family_Ident']]:
        if sibling_id in dp_records_multidict:
            siblingrecord = dp_records_multidict[sibling_id][0]
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
            break

# Clean up outputdata
outputdata_fieldnames = list(DP_REPORT_221_HEADERS)
outputdata_fieldnames.remove('OTHER_ID')
for studentrecord in dp_import_studentrecords:
    del studentrecord['OTHER_ID']
    if len(studentrecord['OTHER_DATE']) == 0:
        studentrecord['OTHER_DATE'] = datetime.date.today().strftime('%m/%d/%Y')

# Write outputdata
with open(sys.argv[3], 'w') as outputfile:
    writer = csv.DictWriter(outputfile, outputdata_fieldnames)
    writer.writeheader()
    for studentrecord in dp_import_studentrecords:
        writer.writerow(studentrecord)
