from __future__ import print_function
from collections import defaultdict
import csv
import datetime
import sys

def usage(error=None):
    if error:
        print("ERROR:", error)
    print('''
Usage: python update_existing_families.py <dp-report-271.csv> <district-data.csv>

Creates files to be imported into DP to update data for existing families.
    <dp-report-271.csv> should be the csv output from DP: Reports -> Custom Report Writer -> 271 -> CSV.
    <district-data.csv> is the Excel spreadsheet received from the district, converted to csv.

Outputs (to current working directory):
    01-student-updates.csv: updates to existing students as well as new students. Import first:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names, Addresses, Other Info
    02-newdonor-updates.csv: creates records for new donors. 
        Import process TBD
    03-donor-updates.csv: updates to existing donors. Import last:
                 TBD
    ''')
    sys.exit(1)

# TODO: Write out family-level updates (address changes etc). These will go to 02-donor-updates.csv.

DP_REPORT_271_HEADERS = ['DONOR_ID','FIRST_NAME','LAST_NAME','SP_FNAME','SP_LNAME',
        'ADDRESS','CITY','STATE','ZIP','EMAIL','SPOUSE_EMAIL',
        'HOME_PHONE','MOBILE_PHONE','SPOUSE_MOBILE',
        'STU_NUMBER','STU_FNAME','STU_LNAME','GRADE','SCHOOL','OTHER_DATE']

DISTRICT_DATA_HEADERS = ['School', 'SystemID', 'Student Last Name', 'Student First Name', 'street', 'city',
                         'state', 'zip', 'Mailing_Street', 'Mailing_City', 'Mailing_State', 'Mailing_Zip',
                         'home_phone', 'Parent1 Last Name', 'Parent 1 First Name', 'Parent 2 Last Name',
                         'Parent 2 First Name', 'Parent1DayPhone', 'Parent2DayPhone', 'Parent1Email',
                         'Parent2Email', 'Guardian', 'GuardianDayPhone', 'GuardianEmail', 'Guardianship',
                         'Grade', 'entrycode', 'entrydate', 'exitdate', 'Family', 'Student', 'Family_Ident',
                         'enroll_status', 'Comment', 'PTA_BCE_Permit']
SCHOOL_YEAR = 'SY2016-17'

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

def dp_grade_for_district_record(district_record):
    # District data uses grade 0 for both TK and Kindergarten
    if district_record['entrycode'] == 'TK':
        return "-1"
    else:
        return district_record['Grade']

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
    print("Number of input records read from %s = %d" % (filename, len(res)))
    return res

def save_as_csv_file(filename, header_fields, data): 
    with open(filename, 'w') as outputfile:
        writer = csv.DictWriter(outputfile, header_fields)
        writer.writeheader()
        for record in data:
            writer.writerow(record)

if len(sys.argv) != 3:
    usage()

dp_report_271_filename = sys.argv[1]
district_data_filename = sys.argv[2]
student_updates_filename = '01-student-updates.csv'
newdonor_filename = '02-newdonor-updates.csv'

# Load dp data keyed off student number
dp_records_multidict = defaultdict(list)
for row in load_csv_file(dp_report_271_filename, DP_REPORT_271_HEADERS):
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
            studentrecord['GRADE'] = dp_grade_for_district_record(district_records_dict[student_id])
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
dp_import_newdonorrecords = []
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
                        'GRADE': dp_grade_for_district_record(district_record),
                        'FIRST_NAME': siblingrecord['FIRST_NAME'],
                        'LAST_NAME': siblingrecord['LAST_NAME'],
                        'SP_FNAME': siblingrecord['SP_FNAME'],
                        'SP_LNAME': siblingrecord['SP_LNAME'],
                        'ADDRESS': siblingrecord['ADDRESS'],
                        'CITY': siblingrecord['CITY'],
                        'STATE': siblingrecord['STATE'],
                        'ZIP': siblingrecord['ZIP'],
                        'EMAIL': siblingrecord['EMAIL'],
                        'SPOUSE_EMAIL': siblingrecord['SPOUSE_EMAIL'],
                        'HOME_PHONE': siblingrecord['HOME_PHONE'],
                        'MOBILE_PHONE': siblingrecord['MOBILE_PHONE'],
                        'SPOUSE_MOBILE': siblingrecord['SPOUSE_MOBILE'],
                        'OTHER_DATE': ''
                    }
                    dp_import_studentrecords.append(studentrecord)

    if len(donor_ids_encountered) == 0:
        # At this point we know that: 
        #   (a) this student isn't in DP (i.e., this is new student)
        #   (b) this student doesn't have an sibling currently in BSD
        # Chances are the donor is also new, unless 
        #   (i) the donor has a kid that has graduated already OR, 
        #   (ii) this student is returning after a break from BSD, but somehow was given a new student ID
        # If either (i) or (ii) is true, then DP will not create a new record, but update the existing donor record, so we should be okay. 
        # At any rate, we have to prepare a new record for this donor, with several custom fields
        #print("Creating record for new donor w/ new student %s" % (student_id))

        main_l_name = district_record['Parent1 Last Name']
        if len(main_l_name) != 0: 
            main_f_name = district_record['Parent 1 First Name']
            spouse_f_name = district_record['Parent 2 First Name']
            spouse_l_name = district_record['Parent 2 Last Name']
        else:
            main_f_name = district_record['Parent 2 First Name']
            main_l_name = district_record['Parent 2 Last Name']
            spouse_f_name = ""
            spouse_l_name = ""


        if len(spouse_l_name) != 0:
            if spouse_l_name == main_l_name :
                salutation = main_f_name + " and " + spouse_f_name + " " + spouse_l_name
            else:
                salutation = main_f_name + " " + main_l_name + " and " + spouse_f_name + " " + spouse_l_name
            informal_sal = main_f_name + " and " + spouse_f_name
        else:
            salutation = main_f_name + " " + main_l_name 
            informal_sal = main_f_name 


        if len(district_record['Parent1Email']) == 0:
            email = district_record['Parent2Email']
        else:
            email = district_record['Parent1Email']
            
            
        newdonorrecord = {
                'FIRST_NAME': main_f_name,
                'LAST_NAME': main_l_name,
                'SP_FNAME': spouse_f_name,
                'SP_LNAME': spouse_l_name,
                'SALUTATION': salutation,
                'INFORMAL_SAL': informal_sal,
                'OPT_LINE': spouse_f_name + " " + spouse_l_name,
                'ADDRESS': district_record['street'],
                'CITY': district_record['city'],
                'STATE': district_record['state'],
                'ZIP': district_record['zip'],
                'ADDRESS_TYPE': 'HOME',
                'EMAIL': email,
                'SPOUSE_EMAIL': district_record['Parent2Email'],
                'HOME_PHONE': district_record['home_phone'],
                'MOBILE_PHONE': district_record['Parent1DayPhone'],
                'SPOUSE_MOBILE': district_record['Parent2DayPhone'],
                'STU_FNAME': district_record['Student First Name'],
                'STU_LNAME': district_record['Student Last Name'],
                'STU_NUMBER': district_record['SystemID'],
                'SCHOOL': district_school_to_dp_school(district_record['School']),
                'GRADE': dp_grade_for_district_record(district_record),
                'GUARDIAN': district_record['Guardian'],
                'GUARD_EMAIL': district_record['GuardianEmail'],
                'DONOR_TYPE': 'IN',
                'FY_JOIN_BSD': SCHOOL_YEAR,
                'RECEIPT_DELIVERY': 'E',
                'OTHER_DATE': datetime.date.today().strftime('%m/%d/%Y'),
                }
        dp_import_newdonorrecords.append(newdonorrecord)

    #End if no donor ID records found
#End loop over student IDs in district data

# Clean up outputdata
outputdata_fieldnames = list(DP_REPORT_271_HEADERS)
for studentrecord in dp_import_studentrecords:
    if len(studentrecord['OTHER_DATE']) == 0:
        studentrecord['OTHER_DATE'] = datetime.date.today().strftime('%m/%d/%Y')

save_as_csv_file(student_updates_filename, outputdata_fieldnames, dp_import_studentrecords)
print("Number of student updated records for upload = %d" % len(dp_import_studentrecords))


# Output new-donor upload file 
newdonor_header = ['FIRST_NAME', 
                'LAST_NAME', 
                'SP_FNAME', 
                'SP_LNAME',
                'SALUTATION',
                'INFORMAL_SAL',
                'OPT_LINE',
                'ADDRESS',
                'CITY',
                'STATE',
                'ZIP',
                'ADDRESS_TYPE',
                'EMAIL',
                'SPOUSE_EMAIL',
                'HOME_PHONE',
                'MOBILE_PHONE',
                'SPOUSE_MOBILE',
                'STU_FNAME',
                'STU_LNAME',
                'STU_NUMBER',
                'SCHOOL',
                'GRADE',
                'GUARDIAN',
                'GUARD_EMAIL',
                'DONOR_TYPE',
                'FY_JOIN_BSD',
                'RECEIPT_DELIVERY',
                'OTHER_DATE' ]

save_as_csv_file(newdonor_filename, newdonor_header, dp_import_newdonorrecords)
print("Number of new donor records for upload = %d" % len(dp_import_newdonorrecords))
