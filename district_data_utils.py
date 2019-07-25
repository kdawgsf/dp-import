import utils

DISTRICT_DATA_HEADERS = ['School', 'SystemID', 'Student Last Name', 'Student First Name', 'Street', 'City',
                         'State', 'Zip', 'Mailing_Street', 'Mailing_City', 'Mailing_State', 'Mailing_Zip',
                         'home_phone', 'Parent 1 Last Name', 'Parent 1 First Name', 'Parent 2 Last Name',
                         'Parent 2 First Name', 'Parent1DayPhone', 'Parent2DayPhone', 'Parent1Email',
                         'Parent2Email', #'guardian', 'guardianemail',
                         'Grade',
                         'Comment',
                         'Entrycode', 'entrydate', 'Enroll_Status', 'FamilyID', 'exitdate']
# 'GuardianDayPhone'

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
    return "-1" if district_record['Grade'] in ['TK','-2'] or district_record['Entrycode'] == 'TK' else district_record['Grade']


def create_dp_studentrecord(district_record):
    """Create a DP studentrecord from the given district record"""
    dp_studentrecord = {
        'STU_LNAME': district_record['Student Last Name'],
        'STU_FNAME': district_record['Student First Name'],
        'STU_NUMBER': district_record['SystemID'],
        'SCHOOL': district_school_to_dp_school(district_record['School']),
        'GRADE': dp_grade_for_district_record(district_record),
        'OTHER_DATE': utils.TODAY_STR
    }
    return dp_studentrecord


def create_salutation(main_f_name, main_l_name, spouse_f_name, spouse_l_name):
    if len(spouse_l_name) != 0:
        if spouse_l_name == main_l_name:
            salutation = main_f_name + " and " + spouse_f_name + " " + spouse_l_name
        else:
            salutation = main_f_name + " " + main_l_name + " and " + spouse_f_name + " " + spouse_l_name
    else:
        salutation = main_f_name + " " + main_l_name
    return salutation


def create_informal_sal(main_f_name, spouse_f_name):
    if len(spouse_f_name) != 0:
        informal_sal = main_f_name + " and " + spouse_f_name
    else:
        informal_sal = main_f_name
    return informal_sal


def create_dp_donorrecord(district_record, school_year):
    """Create a DP donorrecord from the given district record (without creating any studentrecords)."""
    if not school_year:
        raise ValueError("school_year param required")
    main_l_name = district_record['Parent 1 Last Name']
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

    salutation = create_salutation(main_f_name, main_l_name, spouse_f_name, spouse_l_name)
    informal_sal = create_informal_sal(main_f_name, spouse_f_name)

    dp_donorrecord = {
        'FIRST_NAME': main_f_name,
        'LAST_NAME': main_l_name,
        'SP_FNAME': spouse_f_name,
        'SP_LNAME': spouse_l_name,
        'SALUTATION': salutation,
        'INFORMAL_SAL': informal_sal,
        'OPT_LINE': spouse_f_name + " " + spouse_l_name,
        'ADDRESS': district_record['Street'],
        'CITY': district_record['City'],
        'STATE': district_record['State'],
        'ZIP': district_record['Zip'],
        'ADDRESS_TYPE': 'HOME',
        'EMAIL': main_email,
        'SPOUSE_EMAIL': spouse_email,
        'HOME_PHONE': district_record['home_phone'],
        'MOBILE_PHONE': district_record['Parent1DayPhone'],
        'SPOUSE_MOBILE': district_record['Parent2DayPhone'],
        #'GUARDIAN': district_record['guardian'],
        #'GUARD_EMAIL': district_record['guardianemail'],
        'DONOR_TYPE': 'IN',
        'FY_JOIN_BSD': school_year,
        'RECEIPT_DELIVERY': 'E',
        'NOMAIL': 'N',
        'NOMAIL_REASON': ''
    }
    return dp_donorrecord


# See https://stackoverflow.com/questions/2460177/edit-distance-in-python#32558749
def levenshteinDistance(s1, s2):
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]
