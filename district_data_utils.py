import utils

DISTRICT_DATA_HEADERS = ['School', 'SystemID', 'Student Last Name', 'Student First Name', 'street', 'city',
                         'state', 'zip', 'Mailing_Street', 'Mailing_City', 'Mailing_State', 'Mailing_Zip',
                         'home_phone', 'Parent1 Last Name', 'Parent 1 First Name', 'Parent 2 Last Name',
                         'Parent 2 First Name', 'Parent1DayPhone', 'Parent2DayPhone', 'Parent1Email',
                         'Parent2Email', 'Guardian', 'GuardianDayPhone', 'GuardianEmail', 'Guardianship',
                         'Grade', 'entrycode', 'entrydate', 'exitdate', 'Family', 'Student', 'Family_Ident',
                         'enroll_status', 'Comment', 'PTA_BCE_Permit']

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


def create_dp_studentrecord(donor_id, other_id, district_record):
    """Create a DP studentrecord from the given district record"""
    if not donor_id:
        raise ValueError("donor_id param required")
    if not other_id:
        raise ValueError("other_id param required")
    dp_studentrecord = {
        'DONOR_ID': donor_id,
        'STU_LNAME': district_record['Student Last Name'],
        'STU_FNAME': district_record['Student First Name'],
        'STU_NUMBER': district_record['SystemID'],
        'SCHOOL': district_school_to_dp_school(district_record['School']),
        'GRADE': dp_grade_for_district_record(district_record),
        'OTHER_ID': other_id,
        'OTHER_DATE': utils.TODAY_STR
    }
    return dp_studentrecord


def create_dp_donorrecord(donor_id, district_record, school_year):
    """Create a DP donorrecord from the given district record (without creating any studentrecords)."""
    if not donor_id:
        raise ValueError("donor_id param required")
    if not school_year:
        raise ValueError("school_year param required")
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
        if spouse_l_name == main_l_name:
            salutation = main_f_name + " and " + spouse_f_name + " " + spouse_l_name
        else:
            salutation = main_f_name + " " + main_l_name + " and " + spouse_f_name + " " + spouse_l_name
        informal_sal = main_f_name + " and " + spouse_f_name
    else:
        salutation = main_f_name + " " + main_l_name
        informal_sal = main_f_name

    dp_donorrecord = {
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
        'FY_JOIN_BSD': school_year,
        'RECEIPT_DELIVERY': 'E',
        'NOMAIL': 'N',
        'NOMAIL_REASON': ''
    }
    return dp_donorrecord