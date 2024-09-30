# Upload Requirements

## High-level Requirements

1. Update database to graduate 8th grade students (in August only)
1. Use district data to update existing families for new students, school changes, address and e-mail changes
1. Use district data to create records for new families

## Detailed Requirements

1. Graduate students
    * Assumes that incoming 8th grade students have not been updated in database
    * If current grade is 8, set new grade to "Alum", and school to "Graduated from BCD"
1. Update data for existing donors with data from district
    * For August upload, assumes the student grades for new year has been set correctly in district data
    * Add new students to existing families 
    * Update school information to new school within district 
    * If student is not in current list or incoming list set school to "NOBSD" 
    * Update home address and e-mail addresses
1. Create records for new donor families according to following rules
    * New donor record, with DONOR TYPE = Individual
    * DONOR NAME = Husband's name, usually parent1
    * SPOUSE NAME = Wife's name, usually parent2
    * if (different last names) then SALUTATION = Husband's full name + " and " + Wife's full name else SALUTATION = Husband's first name + " and " + Wife's full name
    * OPT LINE = Wife's full name
    * INFORMAL_SAL = Husband's first name + " and " + Wife's first name
    * FY_JOIN_BSD = SY2016-17 (in Aug 2016, the current year)
    * Set GUARDIAN and GUARD_EMAIL fields if they exist in district data
    * Set RECEIPT_DELIVERY = E (Email)
    * If husband's e-mail doesn't exist, set wife's e-mail in EMAIL field

## Detailed Design

### Graduate students

1. Download all current records from the "Donor" table and the "Other" table
1. Update all students whose grade = 8, and set grade = 9
1. In addition, if the school of the 8th graders is BIS, set school to "ALUM"
1. Upload these modified records to DonorPerfect

### Update data for existing donors

### Create records for new donors


    
