import utils

DISTRICT_DATA_HEADERS = ['School', 'SystemID', 'Student Last Name', 'Student First Name', 
                         'Grade','Contact 1 Street', 'Contact 1 City',
                         'Contact 1 State', 'Contact 1 Zip', 'Contact 1 First Name',
                         'Contact 1 Last Name', 'Contact 1 Relationship', 'Contact 1 Phone Type',
                         'Contact 1 Phone', 'Contact 1 Email',
                         'Contact 2 First Name', 'Contact 2 Last Name', 'Contact 2 Relationship',
                         'Contact 2 Phone Type', 'Contact 2 Phone',
                         'Contact 2 Street', 'Contact 2 City', 'Contact 2 State', 
                         'Contact 2 Zip', 'Contact 2 Email']

# Mapping of district school name to dp school code
DISTRICT_SCHOOL_MAPPING = {
    'BIS': 'BIS',
    'Franklin': 'FRANKLIN',
    'Hoover': 'HOOVER',
    'Lincoln': 'LINCOLN',
    'McKinley': 'MCKINLEY',
    'Roosevelt': 'ROOSEVELT',
    'Washington': 'WASHINGTON',
}


def district_school_to_dp_school(name):
    return DISTRICT_SCHOOL_MAPPING[name]


def dp_grade_for_district_record(district_record):
    grade = district_record['Grade']
    if grade == 'TK':
        return '-1'
    elif grade == 'K':
        return '0'

    grade_int = int(grade)
    if (grade_int < -1 or grade_int > 8):
        raise ValueError("Grade %s is out of range" % grade)
    return grade


def create_dp_studentrecord(district_record):
    """Create a DP studentrecord from the given district record"""
    dp_studentrecord = {
        'STU_LNAME': district_record['Student Last Name'].strip(),
        'STU_FNAME': district_record['Student First Name'].strip(),
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


def different_household(district_record):
    #return True if the district record contains two households.
    #it's two household if the two addresses are different AND the second
    #household is mother/father relationship.
    #We only match the first 8 chars of the address as we see lots of different
    #variation on addresses.
    if (district_record['Contact 1 Street'] and district_record['Contact 2 Street']
        and district_record['Contact 1 Street'].strip()[:8] != district_record['Contact 2 Street'].strip()[:8]):
        return district_record['Contact 2 Relationship'] in ('Mother', 'Father')
    return False

def create_dp_donorrecord(district_record, school_year, use_alternate=False, swap_parents=False):
    """Create a DP donorrecord from the given district record (without creating any studentrecords)."""
    if not school_year:
        raise ValueError("school_year param required")
    
    if use_alternate:
        if different_household(district_record):
            main_l_name=district_record['Contact 2 Last Name']
            if not main_l_name:
                return None
            main_f_name = district_record['Contact 2 First Name']
            main_email = district_record['Contact 2 Email']
            main_phone = district_record['Contact 2 Phone']
            street = district_record['Contact 2 Street']
            city = district_record['Contact 2 City']
            zip = district_record['Contact 2 Zip']
            state = district_record['Contact 2 State']
            #alternate household do not have spouse info
            spouse_f_name = ""
            spouse_l_name = ""
            spouse_email=""
            spouse_phone=""
        else:
            return None
    else:
        main_l_name = district_record['Contact 1 Last Name'].strip() 
        if len(main_l_name) != 0:
            main_f_name = district_record['Contact 1 First Name'].strip()
            main_email = district_record['Contact 1 Email'].strip()
            main_phone = district_record['Contact 1 Phone']
            street = district_record['Contact 1 Street'].strip()
            city = district_record['Contact 1 City']
            zip = district_record['Contact 1 Zip']
            state = district_record['Contact 1 State']
            #spouse record is filled in ONLY if the address is the same AND
            # contact 2 relationship is mother/father/stepfather/stepmother
            if different_household(district_record):
                spouse_f_name=""
                spouse_l_name=""
                spouse_email=""
                spouse_phone=""
            else:
                #not a different household but if the contact2 relationship is NOT mother/father/stepmother/stepfather
                #we don't want to include it as the same household.  Sometimes when people
                #are living in multi-generational household, this could list their grandmother, aunt, etc.
                if district_record['Contact 2 Relationship'] in ('Mother','Father','Stepmother','Stepfather'):
                    spouse_f_name = district_record['Contact 2 First Name'].strip()
                    spouse_l_name = district_record['Contact 2 Last Name'].strip()
                    spouse_email = district_record['Contact 2 Email'].strip()
                    spouse_phone=district_record['Contact 2 Phone']
                    if spouse_l_name and swap_parents:
                        #we want to swap the parents in this case
                        main_l_name = district_record['Contact 2 Last Name'].strip()
                        main_f_name = district_record['Contact 2 First Name'].strip()
                        main_email = district_record['Contact 2 Email'].strip()
                        main_phone = district_record['Contact 2 Phone']
                        spouse_f_name = district_record['Contact 1 First Name'].strip()
                        spouse_l_name = district_record['Contact 1 Last Name'].strip()
                        spouse_email = district_record['Contact 1 Email'].strip()
                        spouse_phone=district_record['Contact 1 Phone']
                else:
                    spouse_f_name=""
                    spouse_l_name=""
                    spouse_email=""
                    spouse_phone=""
        else:
            main_f_name = district_record['Contact 2 First Name'].strip()
            main_l_name = district_record['Contact 2 Last Name'].strip()
            main_email = district_record['Contact 2 Email'].strip()
            main_phone = district_record['Contact 2 Phone']
            street = district_record['Contact 2 Street'].strip()
            city = district_record['Contact 2 City']
            zip = district_record['Contact 2 Zip']
            state = district_record['Contact 2 State']            
            spouse_f_name = ""
            spouse_l_name = ""
            spouse_email = ""
            spouse_phone = ""

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
        'ADDRESS': street,
        'CITY': city,
        'STATE': state,
        'ZIP': zip,
        'ADDRESS_TYPE': 'HOME',
        'EMAIL': main_email,
        'SPOUSE_EMAIL': spouse_email,
        'MOBILE_PHONE': main_phone,
        'SPOUSE_MOBILE': spouse_phone,
        'DONOR_TYPE': 'IN',
        'FY_JOIN_BSD': school_year,
        'RECEIPT_DELIVERY': 'E',
        'NOMAIL': 'N',
        'NOMAIL_REASON': '',
        'MAILMERGE_FNAME': main_f_name if main_email else 'no email',
        'SP_MAILMERGE_FNAME': spouse_f_name if spouse_email and spouse_email != main_email else 'no email',
        'HOME_SCHOOL': '',
        'FORMER_ELEM_SCHOOL': ''
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
