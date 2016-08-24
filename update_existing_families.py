from __future__ import print_function
from collections import defaultdict
import csv
import datetime
import sys

# TODO: Make the year code a command-line argument

def usage(error=None):
    if error:
        print("ERROR:", error)
    print('''
Usage: python update_existing_families.py <dp-report-271.csv> <district-data.csv>

Creates files to be imported into DP to update data for existing families.
    <dp-report-271.csv> should be the csv output from DP: Reports -> Custom Report Writer -> 271 -> CSV.
    <district-data.csv> is the Excel spreadsheet received from the district, converted to csv.

Outputs (to current working directory):
    01-student-updates.csv: updates to existing students. Import first:
                 Utilities -> Import,
                 Select Type of Import = Update Existing Records,
                 Select Type of Records = Other Info,
                 Ignore DONOR_ID
    02-new-students.csv: creates new students for existing families. Import second:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names, Addresses, Other Info
    03-new-donors.csv: creates records for new donors (and potentially updates some existing ones) / students. Import third:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names, Addresses, Other Info
    04-donor-updates.csv: updates to existing donors. Import last:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names and Addresses
    05-donor-manual-updates.txt: manual updates to existing donors. Update manually:
                 Look up existing records and apply updates as necessary
    ''')
    sys.exit(1)


DP_REPORT_271_HEADERS = ['DONOR_ID','FIRST_NAME','LAST_NAME','SP_FNAME','SP_LNAME',
                         'ADDRESS','CITY','STATE','ZIP','EMAIL','SPOUSE_EMAIL',
                         'HOME_PHONE','MOBILE_PHONE','SPOUSE_MOBILE',
                         'STU_NUMBER','STU_FNAME','STU_LNAME','GRADE','SCHOOL','OTHER_ID','OTHER_DATE']

DISTRICT_DATA_HEADERS = ['School', 'SystemID', 'Student Last Name', 'Student First Name', 'street', 'city',
                         'state', 'zip', 'Mailing_Street', 'Mailing_City', 'Mailing_State', 'Mailing_Zip',
                         'home_phone', 'Parent1 Last Name', 'Parent 1 First Name', 'Parent 2 Last Name',
                         'Parent 2 First Name', 'Parent1DayPhone', 'Parent2DayPhone', 'Parent1Email',
                         'Parent2Email', 'Guardian', 'GuardianDayPhone', 'GuardianEmail', 'Guardianship',
                         'Grade', 'entrycode', 'entrydate', 'exitdate', 'Family', 'Student', 'Family_Ident',
                         'enroll_status', 'Comment', 'PTA_BCE_Permit']

SCHOOL_YEAR = 'SY2016-17'
TODAY_STR = datetime.date.today().strftime('%m/%d/%Y')
SHOULD_UPDATE_EMAIL = False

FILENAME_STUDENT_UPDATES = '01-student-updates.csv'
FILENAME_NEWSTUDENT = '02-new-students.csv'
FILENAME_NEWDONOR = '03-new-donors.csv'
FILENAME_DONOR_UPDATES = '04-donor-updates.csv'
FILENAME_DONOR_UPDATE_MESSAGES = '05-donor-manual-updates.txt'

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
    print("  %s: Number of input records read = %d" % (filename, len(res)))
    return res

def save_as_csv_file(filename, header_fields, data): 
    with open(filename, 'w') as outputfile:
        writer = csv.DictWriter(outputfile, header_fields)
        writer.writeheader()
        for record in data:
            writer.writerow(record)
    print("  %s: Number of output records for upload = %d" % (filename, len(data)))

def save_as_text_file(filename, messages):
    with open(filename, 'w') as outputfile:
        for message in messages:
            outputfile.write(message)
    print("  %s: Number of output messages = %d" % (filename, len(messages)))

def convert_str_list_to_message(str_list):
    res = ''
    for str in str_list:
        res += str + '\n'
    res += '\n'
    return res

if len(sys.argv) != 3:
    usage()

filename_dp_report_271 = sys.argv[1]
filename_district_data = sys.argv[2]

print("Input files:")

# Load dp data keyed off student number
dp_records_multidict = defaultdict(list)
for row in load_csv_file(filename_dp_report_271, DP_REPORT_271_HEADERS):
    if len(row['STU_NUMBER']) > 0:
        dp_records_multidict[row['STU_NUMBER']].append(row)

# Load district data keyed off student number ("system id" there)
district_records_dict = {}
for row in load_csv_file(filename_district_data, DISTRICT_DATA_HEADERS):
    district_records_dict[row['SystemID']] = row

STUDENT_UPDATES_HEADERS = ['DONOR_ID', 'STU_NUMBER', 'STU_FNAME', 'STU_LNAME', 'SCHOOL', 'GRADE', 'OTHER_ID', 'OTHER_DATE']

# Make updates for existing students
dp_import_existingstudentrecords = []
for student_id in dp_records_multidict:
    for dp_record in dp_records_multidict[student_id]:
        dp_record_minimal = { field: dp_record[field] for field in STUDENT_UPDATES_HEADERS }
        studentrecord = dp_record_minimal.copy()
        if student_id in district_records_dict:
            # Returning student
            studentrecord['GRADE'] = dp_grade_for_district_record(district_records_dict[student_id])
            studentrecord['SCHOOL'] = district_school_to_dp_school(district_records_dict[student_id]['School'])
            # District data has 6th graders at the elementary schools, so manually update these
            if studentrecord['GRADE'] == '6':
                studentrecord['SCHOOL'] = 'BIS'
        elif dp_record['GRADE'] == '8' and dp_record['SCHOOL'] == 'BIS':
            studentrecord['GRADE'] = '9'
            studentrecord['SCHOOL'] = 'ALUM'
        elif dp_record['SCHOOL'] != 'ALUM':
            studentrecord['SCHOOL'] = 'NOBSD'
        # The two records will be the same if:
        # (a) we run this mid-year, OR
        # (b) a student is already NOBSD
        # The same process works whether we're running a summer update or a mid-year update.
        if dp_record_minimal != studentrecord:
            if studentrecord['OTHER_DATE'] == '':
                studentrecord['OTHER_DATE'] = TODAY_STR
            dp_import_existingstudentrecords.append(studentrecord)

# Build up students for each family
students_by_family_ident = defaultdict(list)
for student_id in district_records_dict:
    family_ident = district_records_dict[student_id]['Family_Ident']
    students_by_family_ident[family_ident].append(student_id)

# Add new students, either to existing or new families
dp_import_newdonorrecords = []
dp_import_newstudentrecords = []
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
                        'OTHER_ID': '',
                        'OTHER_DATE': TODAY_STR
                    }
                    dp_import_newstudentrecords.append(studentrecord)

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
                'OTHER_DATE': TODAY_STR,
                }
        dp_import_newdonorrecords.append(newdonorrecord)

    #End if no donor ID records found
#End loop over student IDs in district data

# Identify updates to existing donors
dp_import_existingdonorrecords = []
dp_messages_existingdonorrecords = []
donor_ids_processed = set()
for student_id in district_records_dict:
    district_record = district_records_dict[student_id]
    district_address = '%s %s %s %s' % (district_record['street'], district_record['city'], district_record['state'], district_record['zip'])
    district_emails = set([district_record['Parent1Email'].lower(), district_record['Parent2Email'].lower()])
    district_emails.discard('')

    dp_addresses = set()
    dp_emails = set()
    donor_ids_for_student = set()
    for dp_record in dp_records_multidict[student_id]:
        donor_ids_for_student.add(dp_record['DONOR_ID'])
        dp_addresses.add('%s %s %s %s' % (dp_record['ADDRESS'], dp_record['CITY'], dp_record['STATE'], dp_record['ZIP']))
        dp_emails.add(dp_record['EMAIL'].lower())
        dp_emails.add(dp_record['SPOUSE_EMAIL'].lower())
    dp_emails.discard('')

    if donor_ids_processed.issuperset(donor_ids_for_student):
        continue

    donor_ids_processed.update(donor_ids_for_student)
    if (district_address not in dp_addresses) or (SHOULD_UPDATE_EMAIL and not dp_emails.issuperset(district_emails)):
        if len(donor_ids_for_student) == 1:
            # We will make the update
            dp_record = dp_records_multidict[student_id][0]
            existingdonorrecord = {
                'DONOR_ID': dp_record['DONOR_ID'],
                'ADDRESS': district_record['street'],
                'CITY': district_record['city'],
                'STATE': district_record['state'],
                'ZIP': district_record['zip']
            }
            if SHOULD_UPDATE_EMAIL:
                existingdonorrecord.update({
                    'EMAIL': district_record['Parent1Email'],
                    'SPOUSE_EMAIL': district_record['Parent2Email']
                })
                if existingdonorrecord['EMAIL'] == '':
                    existingdonorrecord['EMAIL'] = existingdonorrecord['SPOUSE_EMAIL']
            dp_import_existingdonorrecords.append(existingdonorrecord)
        else:
            # Don't want to update the wrong donor, so just note the difference
            str_list = []
            str_list.append("Found MANUAL ADDRESS UPDATE for student %s %s (%s) with %d donor records:"
                            % (dp_record['STU_FNAME'], dp_record['STU_LNAME'], student_id, len(donor_ids_for_student)))
            if district_address not in dp_addresses:
                str_list.append("  DP addresses: " + ', '.join(dp_addresses))
                str_list.append("  District address: " + district_address)
            if SHOULD_UPDATE_EMAIL and not dp_emails.issuperset(district_emails):
                str_list.append("  DP emails: " + ', '.join(dp_emails))
                str_list.append("  District Parent1Email: " + district_record['Parent1Email'])
                str_list.append("  District Parent2Email: " + district_record['Parent2Email'])
            dp_messages_existingdonorrecords.append(convert_str_list_to_message(str_list))

print()
print("Output files:")
save_as_csv_file(FILENAME_STUDENT_UPDATES, STUDENT_UPDATES_HEADERS, dp_import_existingstudentrecords)

save_as_csv_file(FILENAME_NEWSTUDENT, STUDENT_UPDATES_HEADERS, dp_import_newstudentrecords)

# Output new-donor upload file
newdonor_header = ['STU_NUMBER',
                'STU_LNAME',
                'STU_FNAME',
                'FIRST_NAME',
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
                'SCHOOL',
                'GRADE',
                'GUARDIAN',
                'GUARD_EMAIL',
                'DONOR_TYPE',
                'FY_JOIN_BSD',
                'RECEIPT_DELIVERY',
                'OTHER_DATE' ]

save_as_csv_file(FILENAME_NEWDONOR, newdonor_header, dp_import_newdonorrecords)

# Output donor-updates upload file
existingdonor_header = ['DONOR_ID', 'ADDRESS', 'CITY', 'STATE', 'ZIP']
if SHOULD_UPDATE_EMAIL:
    existingdonor_header += ['EMAIL', 'SPOUSE_EMAIL']
save_as_csv_file(FILENAME_DONOR_UPDATES, existingdonor_header, dp_import_existingdonorrecords)
save_as_text_file(FILENAME_DONOR_UPDATE_MESSAGES, dp_messages_existingdonorrecords)
