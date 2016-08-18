from __future__ import print_function
import csv
import sys

def usage(error=None):
    if error:
        print("ERROR:", error)
    print('''
Usage: python graduation.py <input.csv> <output.csv>
Graduates all outgoing 8th graders.
    <input.csv> should be the csv output of Reports -> Custom Report Writer -> 221.
    <output.csv> will be a file that can be imported into DP: 
                 Utilities -> Import, 
                 Select Type of Import = Insert New and / or Update Existing Records, 
                 Select Type of Records = Names, Addresses, Other Info
    ''')
    exit(1)

def main():
    """The main routine."""
    if len(sys.argv) != 3:
        usage()
    with open(sys.argv[1], 'rb') as inputfile:
        reader = csv.DictReader(inputfile)
        fieldnames = list(reader.fieldnames)
        # For some reason the report outputs two DONOR_ID columns, but that is not a valid import format
        while fieldnames.count('DONOR_ID') > 1:
            fieldnames.remove('DONOR_ID')
        fieldnames.remove('OTHER_ID')
        with open(sys.argv[2], 'w') as outputfile:
            writer = csv.DictWriter(outputfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                if row['GRADE'] == '8':
                    del row['OTHER_ID']
                    if row['SCHOOL'] == 'BIS':
                        row['SCHOOL'] = 'ALUM'
                    row['GRADE'] = '9'
                    # OTHER_DATE is required for import, so use placeholder value if not present
                    if len(row['OTHER_DATE']) == 0:
                        row['OTHER_DATE'] = '1/1/2000'
                    writer.writerow(row)

if __name__ == '__main__':
    main()
