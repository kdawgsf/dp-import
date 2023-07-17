import argparse

from dpdata import DPData


FILENAME_DONOR_UPDATES = 'donor-updates.csv'


parser = argparse.ArgumentParser()
parser.add_argument("--dp-report",
                    help="csv output from DP: Reports -> Custom Report Writer -> Include \"NO MAIL\" Names -> 271 -> CSV",
                    required=True)
args = parser.parse_args()

print("Input files:")

# Load DP data
dp = DPData(args.dp_report)

dp.scrub_data()

print()
print("Output files:")

# Output csv files for import into DP
dp.write_updated_donors_file(FILENAME_DONOR_UPDATES)


# Print instructions on what to do with everything
print('''
Instructions:
    %s: updates to existing donors. Import:
                 Utilities -> Import,
                 Select Type of Import = Insert New and / or Update Existing Records,
                 Select Type of Records = Names and Addresses,
                 Ignore _modified_fields
''' % (FILENAME_DONOR_UPDATES))
