from __future__ import print_function
from collections import defaultdict
import argparse

from dpdata import DPData
import district_data_utils
import utils


FILENAME_STUDENT_UPDATES = '01-student-updates.csv'
FILENAME_NEWSTUDENT = '02-new-students.csv'
FILENAME_NEWDONOR = '03-new-donors.csv'
FILENAME_DONOR_UPDATES = '04-donor-updates.csv'
FILENAME_DONOR_UPDATE_MESSAGES = '05-donor-manual-updates.txt'


parser = argparse.ArgumentParser()
parser.add_argument("--dp-report",
                    help="csv output from DP: Reports -> Custom Report Writer -> Include \"NO MAIL\" Names -> 271 -> CSV",
                    required=True)
parser.add_argument("--district-data",
                    help="spreadsheet received from the district, converted to csv",
                    required=True)
parser.add_argument("--school-year",
                    help="school year to use for new families, e.g. SY2016-17",
                    required=True)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--new-year-import", help="specify that this is a beginning-of-year import, in which missing 8th graders will be graduated", action="store_true")
group.add_argument("--mid-year-update", help="specify that this is a mid-year update", action="store_true")
args = parser.parse_args()


print("Input files:")


# Load DP data
dp = DPData(args.dp_report)


# Load district data keyed off student number ("SystemID" there)
district_records = {}
for row in utils.load_csv_file(args.district_data, district_data_utils.DISTRICT_DATA_HEADERS):
    district_records[row['SystemID']] = row


# For new-year imports, update grade for all students
# For returning students, this will be overridden on the next step
if args.new_year_import:
    for dp_studentrecord in dp.get_students():
        grade = dp_studentrecord['GRADE']
        if grade and int(grade) < 9:
            dp_studentrecord['GRADE'] = str(1 + int(grade))


# Make updates for existing students
for dp_studentrecord in dp.get_students():
    stu_number = dp_studentrecord['STU_NUMBER']
    if stu_number in district_records:
        # Returning student
        dp_studentrecord['GRADE'] = district_data_utils.dp_grade_for_district_record(district_records[stu_number])
        dp_studentrecord['SCHOOL'] = district_data_utils.district_school_to_dp_school(district_records[stu_number]['School'])
        # District data has 6th graders at the elementary schools, so manually update these
        if dp_studentrecord['GRADE'] == '6':
            dp_studentrecord['SCHOOL'] = 'BIS'
    elif args.new_year_import and dp_studentrecord['GRADE'] == '9' and dp_studentrecord['SCHOOL'] == 'BIS':
        dp_studentrecord['SCHOOL'] = 'ALUM'
    elif dp_studentrecord['SCHOOL'] != 'ALUM':
        dp_studentrecord['SCHOOL'] = 'NOBSD'


# We have 3 different ways to match district records to 1 or more donors. For each student, we use the first successful strategy:
# 1. Match based on SystemID (in district data) / STU_NUMBER (in dp data)
# 2. Match based on being in same family (same Family_Ident in district data) as a student who has existing donors
# 3. Match based on the DP fields that it uses for matching

# Build up students for each family so that we can match new students in each family
family_ident_to_stu_numbers = defaultdict(list)
for stu_number in district_records:
    family_ident = district_records[stu_number]['Family_Ident']
    family_ident_to_stu_numbers[family_ident].append(stu_number)

# Populate match key for all existing donors
match_key_to_donor_id = dict()
for dp_donorrecord in dp.get_donors():
    donor_id = dp_donorrecord['DONOR_ID']
    match_key = dp.compute_match_key(dp_donorrecord)
    if match_key in match_key_to_donor_id:
        print("Hmm, found duplicate match key %s, for donors %s and %s" % (match_key, match_key_to_donor_id[match_key], donor_id))
    match_key_to_donor_id[match_key] = donor_id

# Add new students, either to existing or new families
for stu_number, district_record in district_records.iteritems():
    if dp.get_students_for_stu_number(stu_number):
        continue
    donor_ids_encountered = set()
    for sibling_stu_number in family_ident_to_stu_numbers[district_record['Family_Ident']]:
        for dp_siblingrecord in dp.get_students_for_stu_number(sibling_stu_number):
            donor_id = dp_siblingrecord['DONOR_ID']
            if donor_id not in donor_ids_encountered:
                donor_ids_encountered.add(donor_id)
                dp_studentrecord = district_data_utils.create_dp_studentrecord(district_record)
                dp_studentrecord['DONOR_ID'] = donor_id
                dp_studentrecord['OTHER_ID'] = dp.gen_other_id()
                dp.add_student(dp_studentrecord)

    if not donor_ids_encountered:
        # At this point we know that: 
        #   (a) this student isn't in DP (i.e., this is new student)
        #   (b) this student doesn't have an sibling currently in BSD
        # Chances are the donor is also new, unless 
        #   (i) the donor has a kid that has graduated already OR, 
        #   (ii) this student is returning after a break from BSD, but somehow was given a new student ID
        # If either (i) or (ii) is true, then DP will not create a new record, but update the existing donor record, so we should be okay. 
        # At any rate, we have to prepare a new record for this donor, with several custom fields
        #print("Creating record for new donor w/ new student %s" % (stu_number))
        dp_donorrecord_for_matching = district_data_utils.create_dp_donorrecord(district_record=district_record, school_year=args.school_year)
        match_key = dp.compute_match_key(dp_donorrecord_for_matching)
        if match_key in match_key_to_donor_id:
            # Use the matched donor rather than the one we created for matching purposes
            donor_id = match_key_to_donor_id[match_key]
        else:
            # No match, so go ahead and add the new donor to DP
            donor_id = dp.gen_donor_id()
            match_key_to_donor_id[match_key] = donor_id
            dp_donorrecord_for_matching['DONOR_ID'] = donor_id
            dp.add_donor(dp_donorrecord_for_matching)

        dp_studentrecord = district_data_utils.create_dp_studentrecord(district_record)
        dp_studentrecord['DONOR_ID'] = donor_id
        dp_studentrecord['OTHER_ID'] = dp.gen_other_id()
        dp.add_student(dp_studentrecord)

    #End if no donor ID records found
#End loop over student IDs in district data


# Update GUARD_EMAIL on existing donors
# Requirement is to update this for all donors for a student (if changed)
for stu_number, district_record in district_records.iteritems():
    guard_email = district_record['GuardianEmail']
    if guard_email:
        for dp_studentrecord in dp.get_students_for_stu_number(stu_number):
            dp_donorrecord = dp.get_donor(dp_studentrecord['DONOR_ID'])
            if utils.normalize_email(dp_donorrecord['GUARD_EMAIL']) != utils.normalize_email(guard_email):
                dp_donorrecord['GUARD_EMAIL'] = guard_email


# Compute donor-level updates
for stu_number, district_record in district_records.iteritems():
    dp_studentrecords = dp.get_students_for_stu_number(stu_number)

    if len(dp_studentrecords) == 1:
        # Logic for single-donor students is simpler (typically married parents or only one parent)
        dp_studentrecord = next(iter(dp_studentrecords))
        dp_donorrecord = dp.get_donor(dp_studentrecord['DONOR_ID'])

        # Update address
        dp_donorrecord.update({
            'ADDRESS': district_record['street'],
            'CITY': district_record['city'],
            'STATE': district_record['state'],
            'ZIP': district_record['zip']
        })

        # Update email based on parent1 email
        if district_record['Parent1Email'] and not dp_donorrecord['EMAIL']:
            dp_donorrecord['EMAIL'] = district_record['Parent1Email']

        # Update email based on parent2 email
        parent2_email_field = 'SPOUSE_EMAIL' if district_record['Parent1 Last Name'] else 'EMAIL'
        if district_record['Parent2Email'] and not dp_donorrecord[parent2_email_field]:
            dp_donorrecord[parent2_email_field] = district_record['Parent2Email']
    else:
        # For multi-donor students, typically both Parent1 and Parent2 are separate donors, and the "spouse" is either
        # the ex-spouse or a non-parent spouse. So, we will match the donor's first name against either Parent1 or
        # Parent2's first name and update the email address if applicable.
        for dp_studentrecord in dp_studentrecords:
            dp_donorrecord = dp.get_donor(dp_studentrecord['DONOR_ID'])
            if not dp_donorrecord['EMAIL']:
                if district_record['Parent1Email'] and dp_donorrecord['FIRST_NAME'] == district_record['Parent 1 First Name']:
                    dp_donorrecord['EMAIL'] = district_record['Parent1Email']
                elif district_record['Parent2Email'] and dp_donorrecord['FIRST_NAME'] == district_record['Parent 2 First Name']:
                    dp_donorrecord['EMAIL'] = district_record['Parent2Email']


# Compute manual updates for (most likely) divorced donors
# The goal is to detect if we have fresher data in the district data, then write out notes in a file to
# be processed by someone manually interacting with DP.
dp_messages_existingdonorrecords = list()
dp_messages_donor_ids = set()
for stu_number, district_record in district_records.iteritems():
    dp_studentrecords = dp.get_students_for_stu_number(stu_number)
    if len(dp_studentrecords) < 2:
        continue

    district_address = '%s %s %s %s' % (district_record['street'], district_record['city'], district_record['state'], district_record['zip'])

    # Cases we are trying to detect:
    # 1. District address is not present on any of the donors
    dp_addresses_by_donor_id = dict()
    for dp_studentrecord in dp_studentrecords:
        donor_id = dp_studentrecord['DONOR_ID']
        dp_donorrecord = dp.get_donor(donor_id)
        dp_addresses_by_donor_id[donor_id] = '%s %s %s %s' % (dp_donorrecord['ADDRESS'], dp_donorrecord['CITY'], dp_donorrecord['STATE'], dp_donorrecord['ZIP'])

    donor_ids_for_student = set(dp_addresses_by_donor_id.keys())
    if dp_messages_donor_ids.issuperset(donor_ids_for_student):
        # In this case we have already spat out a message for all donors (because we already encountered a sibling).
        # So, we can skip this student rather than spitting out a duplicate message.
        continue
    else:
        dp_messages_donor_ids.update(donor_ids_for_student)

    flag_address = district_address not in dp_addresses_by_donor_id.values()
    if flag_address:
        str_list = list()
        str_list.append("Found MANUAL UPDATE for student %s %s (%s) with %d donor records:" %
                        (district_record['Student First Name'], district_record['Student Last Name'], stu_number, len(dp_studentrecords)))
        if flag_address:
            for donor_id, dp_address in dp_addresses_by_donor_id.iteritems():
                str_list.append("  Donor %s address: %s" % (donor_id, dp_address))
            str_list.append("  District address: %s" % district_address)
        dp_messages_existingdonorrecords.append('\n'.join(str_list) + '\n\n')


# Do any post-import data scrubbing
dp.scrub_data()


print()
print("Output files:")

# Output csv files for import into DP
dp.write_updated_students_file(FILENAME_STUDENT_UPDATES)
dp.write_new_students_for_existing_donors_file(FILENAME_NEWSTUDENT)
dp.write_new_students_for_new_donors_file(FILENAME_NEWDONOR)
dp.write_updated_donors_file(FILENAME_DONOR_UPDATES)

# Output donor manual updates file
utils.save_as_text_file(FILENAME_DONOR_UPDATE_MESSAGES, dp_messages_existingdonorrecords)


# Print instructions on what to do with everything
print('''
Instructions:
    %s: updates to existing students. Import first:
                 Utilities -> Import,
                 Select Type of Import = Update Existing Records,
                 Select Type of Records = Other Info,
                 Ignore donor_id and _modified_fields
    %s: creates new students for existing families. Import second:
                 Utilities -> Import,
                 Select Type of Import = Insert New Records,
                 Select Type of Records = Other Info
    %s: creates records for new donors (and potentially updates some existing ones) / students. Import third:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names, Addresses, Other Info
    %s: updates to existing donors. Import last:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names and Addresses,
                 Ignore _modified_fields
    %s: manual updates to existing donors. Update manually:
                 Look up existing records and apply updates as necessary
''' % (FILENAME_STUDENT_UPDATES, FILENAME_NEWSTUDENT, FILENAME_NEWDONOR, FILENAME_DONOR_UPDATES, FILENAME_DONOR_UPDATE_MESSAGES))
