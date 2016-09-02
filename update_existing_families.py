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
    <dp-report-271.csv> should be the csv output from DP: Reports -> Custom Report Writer -> Include "NO MAIL" Names -> 271 -> CSV.
    <district-data.csv> is the Excel spreadsheet received from the district, converted to csv.
    ''')
    sys.exit(1)


DP_REPORT_271_DONOR_HEADERS = ['DONOR_ID','FIRST_NAME','LAST_NAME','SP_FNAME','SP_LNAME',
                               'SALUTATION','INFORMAL_SAL','OPT_LINE','ADDRESS_TYPE',
                               'ADDRESS','CITY','STATE','ZIP','EMAIL','SPOUSE_EMAIL',
                               'HOME_PHONE','MOBILE_PHONE','SPOUSE_MOBILE','DONOR_TYPE',
                               'NOMAIL','NOMAIL_REASON','GUARDIAN','GUARD_EMAIL',
                               'FY_JOIN_BSD','RECEIPT_DELIVERY']

DP_REPORT_271_STUDENT_HEADERS = ['DONOR_ID','STU_NUMBER','STU_FNAME','STU_LNAME','GRADE','SCHOOL','OTHER_ID','OTHER_DATE']

DP_REPORT_271_HEADERS = list(set(DP_REPORT_271_DONOR_HEADERS + DP_REPORT_271_STUDENT_HEADERS))

DISTRICT_DATA_HEADERS = ['School', 'SystemID', 'Student Last Name', 'Student First Name', 'street', 'city',
                         'state', 'zip', 'Mailing_Street', 'Mailing_City', 'Mailing_State', 'Mailing_Zip',
                         'home_phone', 'Parent1 Last Name', 'Parent 1 First Name', 'Parent 2 Last Name',
                         'Parent 2 First Name', 'Parent1DayPhone', 'Parent2DayPhone', 'Parent1Email',
                         'Parent2Email', 'Guardian', 'GuardianDayPhone', 'GuardianEmail', 'Guardianship',
                         'Grade', 'entrycode', 'entrydate', 'exitdate', 'Family', 'Student', 'Family_Ident',
                         'enroll_status', 'Comment', 'PTA_BCE_Permit']

SCHOOL_YEAR = 'SY2016-17'
TODAY_STR = datetime.date.today().strftime('%m/%d/%Y')

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
    print("    %s: Number of input records read = %d" % (filename, len(res)))
    return res

def save_as_csv_file(filename, header_fields, data): 
    with open(filename, 'w') as outputfile:
        writer = csv.DictWriter(outputfile, header_fields)
        writer.writeheader()
        for record in data:
            writer.writerow(record)
    print("    %s: Number of output records for upload = %d" % (filename, len(data)))

def save_as_text_file(filename, messages):
    with open(filename, 'w') as outputfile:
        for message in messages:
            outputfile.write(message)
    print("    %s: Number of output messages = %d" % (filename, len(messages)))

def convert_str_list_to_message(str_list):
    res = ''
    for str in str_list:
        res += str + '\n'
    res += '\n'
    return res

last_seq_values = {}
def gen_next_value(seq):
    next = last_seq_values.get(seq, 0) + 1
    last_seq_values[seq] = next
    return next

def gen_donor_id():
    return -1 * gen_next_value('DONOR_ID')

def gen_other_id():
    return -1 * gen_next_value('OTHER_ID')

def modified_fields(old_dict, new_dict):
    fields = []

    removed_keys = set(old_dict.keys()).difference(new_dict.keys())
    if len(removed_keys) > 0:
        raise ValueError('Keys in old dict but not new dict: %s' % str(removed_keys))

    added_keys = set(new_dict.keys()).difference(old_dict.keys())
    if len(added_keys) > 0:
        raise ValueError('Keys in new dict but not old dict: %s' % str(added_keys))

    for key in old_dict.keys():
        if old_dict[key] != new_dict[key]:
            fields.append(key)
    return fields

if len(sys.argv) != 3:
    usage()

filename_dp_report_271 = sys.argv[1]
filename_district_data = sys.argv[2]

print("Input files:")

# DP donors keyed by DONOR_ID
dp_unmodified_donorrecords = {}
dp_donorrecords = {}

# DP students keyed by OTHER_ID
dp_unmodified_studentrecords = {}
dp_studentrecords = {}

# Multi-maps for various ids
dp_donor_id_to_other_ids = defaultdict(list)
dp_stu_number_to_other_ids = defaultdict(list)

# Load DP data
includes_nomail = False
for row in load_csv_file(filename_dp_report_271, DP_REPORT_271_HEADERS):
    # Process donor-level info
    donor_id = row['DONOR_ID']
    dp_donorrecord = dict((header, row[header]) for header in DP_REPORT_271_DONOR_HEADERS)
    if donor_id in dp_donorrecords:
        if dp_donorrecord != dp_unmodified_donorrecords[donor_id]:
            raise ValueError("Unexpected differences in donors. Assumptions must be incorrect. Expected: %s, Actual: %s" %
                             (dp_unmodified_donorrecords[donor_id], dp_donorrecord))
    else:
        dp_unmodified_donorrecords[donor_id] = dp_donorrecord.copy()
        dp_donorrecords[donor_id] = dp_donorrecord

    # Process student-level info
    other_id = row['OTHER_ID']
    if other_id in dp_studentrecords:
        raise ValueError("Found a duplicate OTHER_ID in report 271, the report's assumptions are now violated")
    dp_studentrecord = dict((header, row[header]) for header in DP_REPORT_271_STUDENT_HEADERS)
    dp_unmodified_studentrecords[other_id] = dp_studentrecord.copy()
    dp_studentrecords[other_id] = dp_studentrecord

    # Compute many-to-many relationships
    dp_donor_id_to_other_ids[donor_id].append(other_id)
    if row['STU_NUMBER']:
        dp_stu_number_to_other_ids[row['STU_NUMBER']].append(other_id)

    if row['NOMAIL'] == 'Y':
        includes_nomail = True

if not includes_nomail:
    print("%s must include \"NO MAIL\" donors. Please select 'Include \"NO MAIL\" Names' and regenerate the report." % filename_dp_report_271)
    sys.exit(1)

# Load district data keyed off student number ("system id" there)
district_records = {}
for row in load_csv_file(filename_district_data, DISTRICT_DATA_HEADERS):
    district_records[row['SystemID']] = row

# Make updates for existing students
for (other_id, dp_studentrecord) in dp_studentrecords.iteritems():
    stu_number = dp_studentrecord['STU_NUMBER']
    if stu_number in district_records:
        # Returning student
        dp_studentrecord['GRADE'] = dp_grade_for_district_record(district_records[stu_number])
        dp_studentrecord['SCHOOL'] = district_school_to_dp_school(district_records[stu_number]['School'])
        # District data has 6th graders at the elementary schools, so manually update these
        if dp_studentrecord['GRADE'] == '6':
            dp_studentrecord['SCHOOL'] = 'BIS'
    elif dp_studentrecord['GRADE'] == '8' and dp_studentrecord['SCHOOL'] == 'BIS':
        dp_studentrecord['GRADE'] = '9'
        dp_studentrecord['SCHOOL'] = 'ALUM'
    elif dp_studentrecord['SCHOOL'] != 'ALUM':
        dp_studentrecord['SCHOOL'] = 'NOBSD'

# Build up students for each family
family_ident_to_stu_numbers = defaultdict(list)
for stu_number in district_records:
    family_ident = district_records[stu_number]['Family_Ident']
    family_ident_to_stu_numbers[family_ident].append(stu_number)

# Add new students, either to existing or new families
for stu_number, district_record in district_records.iteritems():
    if stu_number in dp_stu_number_to_other_ids:
        continue
    donor_ids_encountered = set()
    for sibling_stu_number in family_ident_to_stu_numbers[district_record['Family_Ident']]:
        if sibling_stu_number in dp_stu_number_to_other_ids:
            for sibling_other_id in dp_stu_number_to_other_ids[sibling_stu_number]:
                dp_siblingrecord = dp_studentrecords[sibling_other_id]
                donor_id = dp_siblingrecord['DONOR_ID']
                if donor_id not in donor_ids_encountered:
                    donor_ids_encountered.add(donor_id)
                    other_id = gen_other_id()
                    dp_studentrecord = {
                        'DONOR_ID': donor_id,
                        'STU_LNAME': district_record['Student Last Name'],
                        'STU_FNAME': district_record['Student First Name'],
                        'STU_NUMBER': stu_number,
                        'SCHOOL': district_school_to_dp_school(district_record['School']),
                        'GRADE': dp_grade_for_district_record(district_record),
                        'OTHER_ID': other_id,
                        'OTHER_DATE': TODAY_STR
                    }
                    dp_studentrecords[other_id] = dp_studentrecord
                    dp_stu_number_to_other_ids[stu_number].append(other_id)
                    dp_donor_id_to_other_ids[donor_id].append(other_id)

    if len(donor_ids_encountered) == 0:
        # At this point we know that: 
        #   (a) this student isn't in DP (i.e., this is new student)
        #   (b) this student doesn't have an sibling currently in BSD
        # Chances are the donor is also new, unless 
        #   (i) the donor has a kid that has graduated already OR, 
        #   (ii) this student is returning after a break from BSD, but somehow was given a new student ID
        # If either (i) or (ii) is true, then DP will not create a new record, but update the existing donor record, so we should be okay. 
        # At any rate, we have to prepare a new record for this donor, with several custom fields
        #print("Creating record for new donor w/ new student %s" % (stu_number))

        main_l_name = district_record['Parent1 Last Name']
        if len(main_l_name) != 0: 
            main_f_name = district_record['Parent 1 First Name']
            spouse_f_name = district_record['Parent 2 First Name']
            spouse_l_name = district_record['Parent 2 Last Name']
            main_email = district_record['Parent1Email']
            spouse_email = district_record['Parent2Email']
        else:
            main_f_name = district_record['Parent 2 First Name']
            main_l_name = district_record['Parent 2 Last Name']
            spouse_f_name = ""
            spouse_l_name = ""
            main_email = district_record['Parent2Email']
            spouse_email = ""

        if len(spouse_l_name) != 0:
            if spouse_l_name == main_l_name :
                salutation = main_f_name + " and " + spouse_f_name + " " + spouse_l_name
            else:
                salutation = main_f_name + " " + main_l_name + " and " + spouse_f_name + " " + spouse_l_name
            informal_sal = main_f_name + " and " + spouse_f_name
        else:
            salutation = main_f_name + " " + main_l_name 
            informal_sal = main_f_name 

        donor_id = gen_donor_id()
        dp_donorrecords[donor_id] = {
            'DONOR_ID': donor_id,
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
            'EMAIL': main_email,
            'SPOUSE_EMAIL': spouse_email,
            'HOME_PHONE': district_record['home_phone'],
            'MOBILE_PHONE': district_record['Parent1DayPhone'],
            'SPOUSE_MOBILE': district_record['Parent2DayPhone'],
            'GUARDIAN': district_record['Guardian'],
            'GUARD_EMAIL': district_record['GuardianEmail'],
            'DONOR_TYPE': 'IN',
            'FY_JOIN_BSD': SCHOOL_YEAR,
            'RECEIPT_DELIVERY': 'E',
            'NOMAIL': 'N',
            'NOMAIL_REASON': ''
        }

        other_id = gen_other_id()
        dp_studentrecords[other_id] = {
            'DONOR_ID': donor_id,
            'OTHER_ID': other_id,
            'STU_FNAME': district_record['Student First Name'],
            'STU_LNAME': district_record['Student Last Name'],
            'STU_NUMBER': district_record['SystemID'],
            'SCHOOL': district_school_to_dp_school(district_record['School']),
            'GRADE': dp_grade_for_district_record(district_record),
            'OTHER_DATE': TODAY_STR
        }
        dp_donor_id_to_other_ids[donor_id].append(other_id)
        dp_stu_number_to_other_ids[stu_number].append(other_id)

    #End if no donor ID records found
#End loop over student IDs in district data

# Identify updates to existing donors
dp_messages_existingdonorrecords = []
donor_ids_processed = set()
for stu_number, district_record in district_records.iteritems():
    district_address = '%s %s %s %s' % (district_record['street'], district_record['city'], district_record['state'], district_record['zip'])
    district_emails = set([district_record['Parent1Email'].lower(), district_record['Parent2Email'].lower()])
    district_emails.discard('')

    dp_addresses_by_donor_id = {}
    dp_emails = set()
    donor_ids_for_student = set()
    for other_id in dp_stu_number_to_other_ids[stu_number]:
        donor_id = dp_studentrecords[other_id]['DONOR_ID']
        dp_donorrecord = dp_donorrecords[donor_id]
        donor_ids_for_student.add(donor_id)
        dp_addresses_by_donor_id[donor_id] = '%s %s %s %s' % (dp_donorrecord['ADDRESS'], dp_donorrecord['CITY'], dp_donorrecord['STATE'], dp_donorrecord['ZIP'])
        dp_emails.add(dp_donorrecord['EMAIL'].lower())
        dp_emails.add(dp_donorrecord['SPOUSE_EMAIL'].lower())
    dp_emails.discard('')

    if donor_ids_processed.issuperset(donor_ids_for_student):
        continue

    donor_ids_processed.update(donor_ids_for_student)

    if len(donor_ids_for_student) == 1:
        dp_donorrecord = dp_donorrecords[next(iter(donor_ids_for_student))]

        dp_donorrecord.update({
            'ADDRESS': district_record['street'],
            'CITY': district_record['city'],
            'STATE': district_record['state'],
            'ZIP': district_record['zip']
        })

        if district_record['Parent1Email'] and not dp_donorrecord['EMAIL']:
            dp_donorrecord['EMAIL'] = district_record['Parent1Email']

        if district_record['Parent2Email']:
            email_field = 'SPOUSE_EMAIL' if district_record['Parent1 Last Name'] else 'EMAIL'
            if not dp_donorrecord[email_field]:
                dp_donorrecord[email_field] = district_record['Parent2Email']

        if district_record['GuardianEmail'] and dp_donorrecord['GUARD_EMAIL'].lower().strip() != district_record['GuardianEmail'].lower().strip():
            dp_donorrecord['GUARD_EMAIL'] = district_record['GuardianEmail']

    # TODO The else case is multiple records. Need to see if anything changed

    if (district_address not in dp_addresses_by_donor_id.values()) or not dp_emails.issuperset(district_emails):
        if len(donor_ids_for_student) > 1:
            # Don't want to update the wrong donor, so just note the difference
            str_list = []
            str_list.append("Found MANUAL ADDRESS UPDATE for student %s %s (%s) with %d donor records:"
                            % (district_record['Student First Name'], district_record['Student Last Name'], stu_number, len(donor_ids_for_student)))
            if district_address not in dp_addresses_by_donor_id.values():
                for donor_id, dp_address in dp_addresses_by_donor_id.iteritems():
                    str_list.append("  Donor %s address: %s" % (donor_id, dp_address))
                str_list.append("  District address: %s" % district_address)
            if not dp_emails.issuperset(district_emails):
                str_list.append("  DP emails: " + ', '.join(dp_emails))
                str_list.append("  District Parent1Email: " + district_record['Parent1Email'])
                str_list.append("  District Parent2Email: " + district_record['Parent2Email'])
            dp_messages_existingdonorrecords.append(convert_str_list_to_message(str_list))


# Data cleansing
for donor_id, dp_donorrecord in dp_donorrecords.iteritems():
    # TODO Enable NOMAIL for donors with all NOBSD students
    # TODO Disable NOMAIL for donors with non-NOBSD students and reason NO
    # Empty out NOMAIL_REASON if NOMAIL not set
    if dp_donorrecord['NOMAIL'] == 'N' and dp_donorrecord['NOMAIL_REASON']:
        dp_donorrecord['NOMAIL_REASON'] = ''

def list_with_mods(l, add=[], remove=[]):
    res = l + add
    for v in remove:
        res.remove(v)
    return res

def dict_filtered_copy(dict_to_copy, keys_to_copy):
    res = {}
    for key in keys_to_copy:
        if key in dict_to_copy:
            res[key] = dict_to_copy[key]
    return res

print()
print("Output files:")

# Write student updates file
data = []
headers = list_with_mods(DP_REPORT_271_STUDENT_HEADERS, add=['_MODIFIED_FIELDS'])
for other_id, dp_studentrecord in dp_studentrecords.iteritems():
    if other_id in dp_unmodified_studentrecords and dp_studentrecord != dp_unmodified_studentrecords[other_id]:
        row = dict_filtered_copy(dp_studentrecord, headers)
        row['_MODIFIED_FIELDS'] = '|'.join(modified_fields(dp_unmodified_studentrecords[other_id], dp_studentrecord))
        # Add OTHER_DATE if missing as the import doesn't seem to like having an empty one
        if not row['OTHER_DATE']:
            row['OTHER_DATE'] = TODAY_STR
        data.append(row)
save_as_csv_file(FILENAME_STUDENT_UPDATES, headers, data)

# Write new students (existing donors) file
data = []
headers = list_with_mods(DP_REPORT_271_STUDENT_HEADERS, remove=['OTHER_ID'])
for other_id, dp_studentrecord in dp_studentrecords.iteritems():
    if other_id not in dp_unmodified_studentrecords and dp_studentrecord['DONOR_ID'] in dp_unmodified_donorrecords:
        row = dict_filtered_copy(dp_studentrecord, headers)
        data.append(row)
save_as_csv_file(FILENAME_NEWSTUDENT, headers, data)

# Write new donors (new students) file
data = []
headers = list_with_mods(DP_REPORT_271_HEADERS, remove=['DONOR_ID','OTHER_ID'])
for other_id, dp_studentrecord in dp_studentrecords.iteritems():
    if other_id not in dp_unmodified_studentrecords and dp_studentrecord['DONOR_ID'] not in dp_unmodified_donorrecords:
        # Combine donor and student fields into a single row
        row = dict_filtered_copy(dp_studentrecord, headers)
        row.update(dict_filtered_copy(dp_donorrecords[dp_studentrecord['DONOR_ID']], headers))
        data.append(row)
save_as_csv_file(FILENAME_NEWDONOR, headers, data)

# Write donor updates file
data = []
headers = list_with_mods(DP_REPORT_271_DONOR_HEADERS, add=['_MODIFIED_FIELDS'])
for donor_id, dp_donorrecord in dp_donorrecords.iteritems():
    if donor_id in dp_unmodified_donorrecords and dp_donorrecord != dp_unmodified_donorrecords[donor_id]:
        row = dict_filtered_copy(dp_donorrecord, headers)
        row['_MODIFIED_FIELDS'] = '|'.join(modified_fields(dp_unmodified_donorrecords[donor_id], dp_donorrecord))
        data.append(row)
save_as_csv_file(FILENAME_DONOR_UPDATES, headers, data)

# Output donor manual updates file
save_as_text_file(FILENAME_DONOR_UPDATE_MESSAGES, dp_messages_existingdonorrecords)

print('''
Instructions:
    01-student-updates.csv: updates to existing students. Import first:
                 Utilities -> Import,
                 Select Type of Import = Update Existing Records,
                 Select Type of Records = Other Info,
                 Ignore donor_id and _modified_fields
    02-new-students.csv: creates new students for existing families. Import second:
                 Utilities -> Import,
                 Select Type of Import = Insert New Records,
                 Select Type of Records = Other Info
    03-new-donors.csv: creates records for new donors (and potentially updates some existing ones) / students. Import third:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names, Addresses, Other Info
    04-donor-updates.csv: updates to existing donors. Import last:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names and Addresses,
                 Ignore _modified_fields
    05-donor-manual-updates.txt: manual updates to existing donors. Update manually:
                 Look up existing records and apply updates as necessary
''')
