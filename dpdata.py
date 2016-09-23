from collections import defaultdict, OrderedDict

import utils

DP_REPORT_271_DONOR_HEADERS = ['DONOR_ID','FIRST_NAME','LAST_NAME','SP_FNAME','SP_LNAME',
                               'SALUTATION','INFORMAL_SAL','OPT_LINE','ADDRESS_TYPE',
                               'ADDRESS','CITY','STATE','ZIP','EMAIL','SPOUSE_EMAIL',
                               'HOME_PHONE','MOBILE_PHONE','SPOUSE_MOBILE','DONOR_TYPE',
                               'NOMAIL','NOMAIL_REASON','GUARDIAN','GUARD_EMAIL',
                               'FY_JOIN_BSD','RECEIPT_DELIVERY']

DP_REPORT_271_STUDENT_HEADERS = ['DONOR_ID','STU_NUMBER','STU_FNAME','STU_LNAME','GRADE','SCHOOL','OTHER_ID','OTHER_DATE']

DP_REPORT_271_HEADERS = list(set(DP_REPORT_271_DONOR_HEADERS + DP_REPORT_271_STUDENT_HEADERS))


class DPData:
    # These are the default match fields (and number of chars to compare) for DP donors
    __DONOR_MATCH_FIELDS = OrderedDict([('LAST_NAME', 10), ('FIRST_NAME', 8), ('ADDRESS', 8), ('ZIP', 5)])

    def __init__(self, dp_report_filename):
        self.__donorrecords = dict()
        self.__unmodified_donorrecords = dict()
        self.__studentrecords = dict()
        self.__unmodified_studentrecords = dict()
        self.__donor_id_to_other_ids = defaultdict(list)
        self.__stu_number_to_other_ids = defaultdict(list)
        self.__last_seq_values = dict()
        if dp_report_filename:
            self.__load_dp_report(dp_report_filename)

    def __load_dp_report(self, dp_report_filename):
        includes_nomail = False
        for row in utils.load_csv_file(dp_report_filename, DP_REPORT_271_HEADERS):
            # Process donor-level info
            donor_id = row['DONOR_ID']
            donorrecord = dict((header, row[header]) for header in DP_REPORT_271_DONOR_HEADERS)
            if donor_id in self.__donorrecords:
                if donorrecord != self.__unmodified_donorrecords[donor_id]:
                    raise ValueError(
                        "Unexpected differences in donors. Assumptions must be incorrect. Expected: %s, Actual: %s" %
                        (self.__unmodified_donorrecords[donor_id], donorrecord))
            else:
                self.add_donor(donorrecord)
                self.__unmodified_donorrecords[donor_id] = donorrecord.copy()

            # Process student-level info
            other_id = row['OTHER_ID']
            if other_id in self.__studentrecords:
                raise ValueError("Found a duplicate OTHER_ID in report 271, the report's assumptions are now violated")
            studentrecord = dict((header, row[header]) for header in DP_REPORT_271_STUDENT_HEADERS)
            self.add_student(studentrecord)
            self.__unmodified_studentrecords[other_id] = studentrecord.copy()

            if row['NOMAIL'] == 'Y':
                includes_nomail = True

        if not includes_nomail:
            raise ValueError("%s must include \"NO MAIL\" donors. Please select 'Include \"NO MAIL\" Names' and regenerate the report." % dp_report_filename)

    def __next_seq_value(self, seq):
        next = self.__last_seq_values.get(seq, 0) + 1
        self.__last_seq_values[seq] = next
        return next

    def gen_donor_id(self):
        return str(-1 * self.__next_seq_value('DONOR_ID'))

    def gen_other_id(self):
        return str(-1 * self.__next_seq_value('OTHER_ID'))

    def add_donor(self, donorrecord):
        if 'DONOR_ID' not in donorrecord:
            raise ValueError("DONOR_ID required")
        donor_id = donorrecord['DONOR_ID']
        if donor_id in self.__donorrecords:
            raise ValueError("DONOR_ID %s already present" % donor_id)
        self.__donorrecords[donor_id] = donorrecord

    def get_donor(self, donor_id):
        return self.__donorrecords[donor_id]

    def get_donors(self):
        return self.__donorrecords.values()

    def add_student(self, studentrecord):
        if 'DONOR_ID' not in studentrecord:
            raise ValueError("DONOR_ID required")
        donor_id = studentrecord['DONOR_ID']
        other_id = studentrecord['OTHER_ID']
        if not other_id:
            raise ValueError("OTHER_ID required")
        if other_id in self.__studentrecords:
            raise ValueError("OTHER_ID %s already present" % other_id)
        self.__studentrecords[other_id] = studentrecord
        self.__donor_id_to_other_ids[donor_id].append(other_id)
        if studentrecord['STU_NUMBER']:
            self.__stu_number_to_other_ids[studentrecord['STU_NUMBER']].append(other_id)

    def get_student(self, other_id):
        if other_id in self.__studentrecords:
            return self.__studentrecords[other_id].copy()
        else:
            return None

    def get_students(self):
        return self.__studentrecords.values()

    def get_students_for_donor(self, donor_id):
        res = list()
        for other_id in self.__donor_id_to_other_ids[donor_id]:
            res.append(self.get_student(other_id))
        return res

    def get_students_for_stu_number(self, stu_number):
        res = list()
        for other_id in self.__stu_number_to_other_ids[stu_number]:
            res.append(self.get_student(other_id))
        return res

    def scrub_data(self):
        self.__fixup_nomail_flag()
        self.__copy_spouse_email()

    def __fixup_nomail_flag(self):
        # Fix up NOMAIL stuff
        for dp_donorrecord in self.get_donors():
            donor_id = dp_donorrecord['DONOR_ID']
            dp_studentrecords = self.get_students_for_donor(donor_id)

            student_count_district = 0
            student_count_nobsd = 0
            student_count_converted_to_nobsd = 0

            for dp_studentrecord in dp_studentrecords:
                if dp_studentrecord['SCHOOL'] not in ['ALUM','NOBSD']:
                    student_count_district += 1
                elif dp_studentrecord['SCHOOL'] == 'NOBSD':
                    student_count_nobsd += 1
                    if self.__unmodified_studentrecords[dp_studentrecord['OTHER_ID']]['SCHOOL'] != 'NOBSD':
                        student_count_converted_to_nobsd += 1

            if dp_donorrecord['NOMAIL'] == 'N' and student_count_district == 0:
                # Donor has no current students...
                # If all students are NOBSD, then they get flipped to NO
                # Or if they removed kids from the district, then they get flipped to NO
                # The other case here is various combinations of ALUM students
                if student_count_nobsd == len(dp_studentrecords) or student_count_converted_to_nobsd > 0:
                    dp_donorrecord['NOMAIL'] = 'Y'
                    dp_donorrecord['NOMAIL_REASON'] = 'NO'
                    dp_donorrecord['DONOR_TYPE'] = 'NO'
            elif dp_donorrecord['NOMAIL'] == 'Y' and dp_donorrecord['NOMAIL_REASON'] == 'NO' and student_count_district > 0:
                # They have kids in the district, so we need to unset NOMAIL
                dp_donorrecord['NOMAIL'] = 'N'
                dp_donorrecord['NOMAIL_REASON'] = ''
                dp_donorrecord['DONOR_TYPE'] = 'IN'

            # Legacy data cleanup
            if dp_donorrecord['NOMAIL'] == 'N' and dp_donorrecord['NOMAIL_REASON']:
                # Empty out NOMAIL_REASON if NOMAIL not set
                dp_donorrecord['NOMAIL_REASON'] = ''

    def __copy_spouse_email(self):
        # we need to have email field populated even if the district has no parent1 email
        for dp_donorrecord in self.get_donors():
            if dp_donorrecord['SPOUSE_EMAIL'] and not dp_donorrecord['EMAIL']:
                dp_donorrecord['EMAIL'] = dp_donorrecord['SPOUSE_EMAIL']

    def write_updated_students_file(self, csv_filename):
        data = list()
        headers = utils.list_with_mods(DP_REPORT_271_STUDENT_HEADERS, add=['_MODIFIED_FIELDS'])
        for other_id, studentrecord in self.__studentrecords.iteritems():
            if int(other_id) >= 0 and studentrecord != self.__unmodified_studentrecords[other_id]:
                row = utils.dict_filtered_copy(studentrecord, headers)
                row['_MODIFIED_FIELDS'] = '|'.join(self.__get_modified_fields(studentrecord))
                # Add OTHER_DATE if missing as the import doesn't seem to like having an empty one
                if not row['OTHER_DATE']:
                    row['OTHER_DATE'] = utils.TODAY_STR
                data.append(row)
        utils.save_as_csv_file(csv_filename, headers, data)

    def write_new_students_for_existing_donors_file(self, csv_filename):
        data = list()
        headers = utils.list_with_mods(DP_REPORT_271_STUDENT_HEADERS, remove=['OTHER_ID'])
        for other_id, studentrecord in self.__studentrecords.iteritems():
            if int(other_id) < 0 and int(studentrecord['DONOR_ID']) >= 0:
                row = utils.dict_filtered_copy(studentrecord, headers)
                data.append(row)
        utils.save_as_csv_file(csv_filename, headers, data)

    def write_new_students_for_new_donors_file(self, csv_filename):
        data = list()
        headers = utils.list_with_mods(DP_REPORT_271_HEADERS, remove=['DONOR_ID', 'OTHER_ID'])
        for other_id, studentrecord in self.__studentrecords.iteritems():
            if int(other_id) < 0 and int(studentrecord['DONOR_ID']) < 0:
                # Combine donor and student fields into a single row
                row = utils.dict_filtered_copy(studentrecord, headers)
                row.update(utils.dict_filtered_copy(self.get_donor(studentrecord['DONOR_ID']), headers))
                data.append(row)
        utils.save_as_csv_file(csv_filename, headers, data)

    def write_updated_donors_file(self, csv_filename):
        data = []
        headers = utils.list_with_mods(DP_REPORT_271_DONOR_HEADERS, add=['_MODIFIED_FIELDS'])
        for donor_id, donorrecord in self.__donorrecords.iteritems():
            if int(donor_id) >= 0 and donorrecord != self.__unmodified_donorrecords[donor_id]:
                row = utils.dict_filtered_copy(donorrecord, headers)
                row['_MODIFIED_FIELDS'] = '|'.join(self.__get_modified_fields(donorrecord))
                data.append(row)
        utils.save_as_csv_file(csv_filename, headers, data)

    def __get_modified_fields(self, donor_or_student):
        if donor_or_student.has_key('OTHER_ID'):
            return utils.modified_fields(self.__unmodified_studentrecords[donor_or_student['OTHER_ID']], donor_or_student)
        else:
            return utils.modified_fields(self.__unmodified_donorrecords[donor_or_student['DONOR_ID']], donor_or_student)

    def compute_match_key(self, donorrecord):
        """Returns a string representing the concatenation of all the match key values, trimmed/padded to size"""
        key = ''
        for field, chars_to_compare in self.__DONOR_MATCH_FIELDS.iteritems():
            key += donorrecord.get(field).translate(None, ' -')[:chars_to_compare].upper().ljust(chars_to_compare)
        return key
