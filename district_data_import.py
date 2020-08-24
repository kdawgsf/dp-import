from __future__ import print_function
from datetime import datetime
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
                    help="csv output from DP: Reports -> Report Center -> 271 Name Contacts Other -> Include \"NO MAIL\" Names -> run report -> export as .csv",
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
status_counts = {}
preschool_count = 0
empty_parent_count = 0
for row in utils.load_csv_file(args.district_data, district_data_utils.DISTRICT_DATA_HEADERS):
    enroll_status = row['Enroll_Status']
    if enroll_status not in ['Pre-Registered', 'Returning']:
        status_counts[enroll_status] = 1 + status_counts.get(enroll_status, 0)
    else:
        if row['School'] == 'PreSchool':
            preschool_count += 1
        elif not (row['Parent 1 Last Name'] or row['Parent 2 Last Name']):
            empty_parent_count += 1
        else:
            district_records[row['SystemID']] = row

for (status, count) in status_counts.iteritems():
    print("Ignored %d district records with Enroll_Status of '%s'" % (count, status))
if preschool_count > 0:
    print("Ignored %d district records with a school of PreSchool" % (empty_parent_count))
if empty_parent_count > 0:
    print("Ignored %d district records with no parents" % (empty_parent_count))

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
        dp_studentrecord['YEARTO'] = str(datetime.now().year)
    elif dp_studentrecord['SCHOOL'] not in ['ALUM','NOBSD']:
        dp_studentrecord['SCHOOL'] = 'NOBSD'
        dp_studentrecord['YEARTO'] = str(datetime.now().year)


# We have 2 different ways to match district records to 1 or more donors. For each student, we use the first successful strategy:
# 1. Match based on SystemID (in district data) / STU_NUMBER (in dp data)
# 2. Match based on the DP fields that it uses for matching

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

    # At this point we know that: 
    #   (a) this student isn't in DP (i.e., this is new student)
    # Chances are the donor is also new, unless 
    #   (i) this is a new student on an existing family, and DP will match against the existing donor
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

#End loop over student IDs in district data


# Update GUARD_EMAIL on existing donors
# Requirement is to update this for all donors for a student (if changed)
for stu_number, district_record in district_records.iteritems():
    guard_email = district_record['guardianemail']
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
            'ADDRESS': district_record['Street'],
            'CITY': district_record['City'],
            'STATE': district_record['State'],
            'ZIP': district_record['Zip']
        })

        dp_donorrecord_for_update = district_data_utils.create_dp_donorrecord(district_record=district_record, school_year=args.school_year)

        # Figure out if we are changing the parent order by importing the district data
        parent_order_changed = False
        old_informal_sal_upper = district_data_utils.create_informal_sal(dp_donorrecord['FIRST_NAME'], dp_donorrecord['SP_FNAME']).upper()
        new_informal_sal_upper = district_data_utils.create_informal_sal(dp_donorrecord_for_update['FIRST_NAME'], dp_donorrecord_for_update['SP_FNAME']).upper()
        if old_informal_sal_upper != new_informal_sal_upper and len(dp_donorrecord_for_update['SP_LNAME']) > 0:
            # Something changed, so use edit distance to see if this looks like a parent order swap
            old_informal_sal_reversed_upper = district_data_utils.create_informal_sal(dp_donorrecord['SP_FNAME'], dp_donorrecord['FIRST_NAME']).upper()
            parent_order_changed = district_data_utils.levenshteinDistance(old_informal_sal_reversed_upper, new_informal_sal_upper) < district_data_utils.levenshteinDistance(old_informal_sal_upper, new_informal_sal_upper)

        # Update for potential switch of parent name order (email handled below)
        dp_donorrecord.update({
            'FIRST_NAME': dp_donorrecord_for_update['FIRST_NAME'],
            'LAST_NAME': dp_donorrecord_for_update['LAST_NAME'],
            'SP_FNAME': dp_donorrecord_for_update['SP_FNAME'],
            'SP_LNAME': dp_donorrecord_for_update['SP_LNAME'],
            'MOBILE_PHONE': dp_donorrecord_for_update['MOBILE_PHONE'],
            'SPOUSE_MOBILE': dp_donorrecord_for_update['SPOUSE_MOBILE'],
            'OPT_LINE': dp_donorrecord_for_update['OPT_LINE']
        })

        # If parent order changed, then swap employer, advisory member, and mailmerge first name, and email
        if parent_order_changed:
            dp_donorrecord.update({
                'DONOR_EMPLOYER': dp_donorrecord['SP_EMPLOYER'],
                'SP_EMPLOYER': dp_donorrecord['DONOR_EMPLOYER'],
                'ADVISORY_MEMBER_MULTICODE': dp_donorrecord['SP_ADVISOR_MEMBER_MULTICODE'],
                'SP_ADVISOR_MEMBER_MULTICODE': dp_donorrecord['ADVISORY_MEMBER_MULTICODE'],
                'MAILMERGE_FNAME': dp_donorrecord['SP_MAILMERGE_FNAME'],
                'SP_MAILMERGE_FNAME': dp_donorrecord['MAILMERGE_FNAME'],
                'EMAIL': dp_donorrecord['SPOUSE_EMAIL'],
                'SPOUSE_EMAIL': dp_donorrecord['EMAIL']
            })

        # Only overwrite email if provided by district
        if dp_donorrecord_for_update['EMAIL']:
            dp_donorrecord['EMAIL'] = dp_donorrecord_for_update['EMAIL']
        if dp_donorrecord_for_update['SPOUSE_EMAIL']:
            dp_donorrecord['SPOUSE_EMAIL'] = dp_donorrecord_for_update['SPOUSE_EMAIL']

        #after updating emails, deail with mailmerge fname fields
        #we always want to have a real first name in mailmerge fname if there is email for the donor,
        #particularly after getting any updates from district and after swapping parents.
        if dp_donorrecord['EMAIL']:
            mailmerge_fname = dp_donorrecord['MAILMERGE_FNAME']
            if not mailmerge_fname or mailmerge_fname.lower() == 'no email':
                dp_donorrecord['MAILMERGE_FNAME'] = dp_donorrecord['FIRST_NAME']
        else:
            dp_donorrecord['MAILMERGE_FNAME'] = 'no email'

        #for the spouse mailmerge, it can be 'no email' or set to first name
        #set it to first_name (or keep the existing name) if they have different emails.
        #set to no email if they have the same emails or do not have spouse email.
        if dp_donorrecord['SPOUSE_EMAIL']:
            sp_mailmerge_fname = dp_donorrecord['SP_MAILMERGE_FNAME']
            if dp_donorrecord['EMAIL'].lower() == dp_donorrecord['SPOUSE_EMAIL'].lower():
                dp_donorrecord['SP_MAILMERGE_FNAME'] = 'no email'
            elif not sp_mailmerge_fname or sp_mailmerge_fname.lower() == 'no email':
                dp_donorrecord['SP_MAILMERGE_FNAME'] = dp_donorrecord['SP_FNAME']
        else:
            dp_donorrecord['SP_MAILMERGE_FNAME'] = 'no email'


        # For informal salutations, we update it only if it is a straightforward switch of the parent name order.
        # If the computed value is not a straightforward switch, it indicates that a manual update may have occured based on 
        # personal knowledge of nicknames and such, so we leave it alone. 

        curr_informal_sal = dp_donorrecord['INFORMAL_SAL']
        reversed_auto_informal_sal = district_data_utils.create_informal_sal(dp_donorrecord['SP_FNAME'], dp_donorrecord['FIRST_NAME'])
        if curr_informal_sal == reversed_auto_informal_sal: # Informal salutation has not been personalized
            dp_donorrecord.update({ 
                'SALUTATION': dp_donorrecord_for_update['SALUTATION'],
                'INFORMAL_SAL': dp_donorrecord_for_update['INFORMAL_SAL']
            })

        # Update email based on parent1 email
        if district_record['Parent1Email'] and not dp_donorrecord['EMAIL']:
            dp_donorrecord['EMAIL'] = district_record['Parent1Email']

        # Update email based on parent2 email
        parent2_email_field = 'SPOUSE_EMAIL' if district_record['Parent 1 Last Name'] else 'EMAIL'
        if district_record['Parent2Email'] and not dp_donorrecord[parent2_email_field]:
            dp_donorrecord[parent2_email_field] = district_record['Parent2Email']

        #set homeschool IF needs to be changed by looking at all students for the donor
        #by this time, all students have been promoted and set to their new school
        all_students = dp.get_students_for_donor(dp_studentrecord['DONOR_ID'])
        old_homeschool = dp_donorrecord['HOME_SCHOOL']  #save this for setting the former_elem_school later
        dp_donorrecord['HOME_SCHOOL'] = dp.calculate_homeschool(all_students)

        #set former_elementary_school if not set already
        if not dp_donorrecord['FORMER_ELEM_SCHOOL'] and dp_donorrecord['HOME_SCHOOL'] == 'BIS':
            dp_donorrecord['FORMER_ELEM_SCHOOL'] = '' if old_homeschool in ('BIS','NULL') else old_homeschool

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
            #set homeschool if needs to be changed by looking at all students for the donor
            all_students = dp.get_students_for_donor(dp_studentrecord['DONOR_ID'])
            old_homeschool = dp_donorrecord['HOME_SCHOOL']
            dp_donorrecord['HOME_SCHOOL'] = dp.calculate_homeschool(all_students)
            if not dp_donorrecord['FORMER_ELEM_SCHOOL'] and dp_donorrecord['HOME_SCHOOL'] == 'BIS':
                dp_donorrecord['FORMER_ELEM_SCHOOL'] = '' if old_homeschool == 'BIS' else old_homeschool

# Compute manual updates for (most likely) divorced donors
# The goal is to detect if we have fresher data in the district data, then write out notes in a file to
# be processed by someone manually interacting with DP.
dp_messages_existingdonorrecords = list()
dp_messages_donor_ids = set()
for stu_number, district_record in district_records.iteritems():
    dp_studentrecords = dp.get_students_for_stu_number(stu_number)
    if len(dp_studentrecords) < 2:
        continue

    district_address = '%s %s %s %s' % (district_record['Street'], district_record['City'], district_record['State'], district_record['Zip'])

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
                 When importing this file: Update existing records in a specific table,
                 My import file includes: Other Info,
                 Record matching: Off,
                 Ignore donor_id and _modified_fields
    %s: creates new students for existing families. Import second:
                 Utilities -> Import,
                 When importing this file: Insert new transaction records for existing donors,
                 My import file includes: Other Info,
                 Record matching: Off
    %s: creates records for new donors (and potentially updates some existing ones) / students. Import third:
                 Utilities -> Import,
                 When importing this file: Update Existing Records then insert the rest as new,
                 My import file includes: Main Records and Other Info Transactions,
                 Record matching: On
    %s: updates to existing donors. Import last:
                 Utilities -> Import,
                 When importing this file: Update Existing Records then insert the rest as new,
                 My import file includes: Main Records Only,
                 Record matching: On,
                 Ignore _modified_fields
    %s: manual updates to existing donors. Update manually:
                 Look up existing records and apply updates as necessary
''' % (FILENAME_STUDENT_UPDATES, FILENAME_NEWSTUDENT, FILENAME_NEWDONOR, FILENAME_DONOR_UPDATES, FILENAME_DONOR_UPDATE_MESSAGES))
