### Prepping for the import

First, make sure you have python 2.7.

Next, create a new directory for the import:

```
mkdir Upload-Archive-<yyyymmdd>
cd Upload-Archive-<yyyymmdd>
mkdir GeneratedFiles
mkdir ImportResults
```

### Create district data csv file

The district provides an excel spreadsheet with the data we need. This spreadsheet has a some header info above the column headers that we need to remove, and we also need to convert it to csv:

1. Open the file in Excel
2. Remove the rows about the column headers
3. Save csv to our Upload-Archive directory: File -> Save As... -> Format: Comma Separated Values (.csv).

### Create DP export file

Now we need to create an export of donors and students from DP:

1. Log in to DP
2. Navigate to Reports -> Report Center
3. Click on "271 Name Contacts Other"
4. On the left-hand sidebar, ensure the Include "NO MAIL" Names checkbox is checked
5. Hover over the arrow to the right of the "run report" button and click on "export as .csv"
6. Click OK to run the report without a filter
7. Copy the downloaded csv file into the Upload-Archive directory

The last time I ran the report, it produced a csv file in utf-8 encoding, which was not compatible with the script. To reformat the csv file, we must take these steps:

1. Open the file in Excel
2. Change the header in column A1 to "GRADE" (without the quotes) to remove any special formatting. (This was tested in Excel for Mac 2011.)
3. Save the file. That's it!

> Note: As of July 2020, this step did not need to be performed.

## Running the script

There are two ways to run the script: a new-year import and a mid-year import. The main difference is how the script deals with 8th graders that are present in DP but not in the district data. A new-year import marks these students as alums while a mid-year import marks them as having left the district.

In addition to the two input csv files and what kind of import this is, you'll also need to know the school year, which will be formatted like "SY2016-17". Here are some example import commands, as run from the GeneratedFiles directory:

```
# New-year update
python ../../district_data_import.py --dp-report ../271_Name_Contacts_Other.csv --district-data ../district_data_20170317.csv --school-year SY2016-17 --new-year-import >script_output.txt

# Mid-year update
python ../../district_data_import.py --dp-report ../271_Name_Contacts_Other.csv --district-data ../district_data_20170317.csv --school-year SY2016-17 --mid-year-update >script_output.txt
```

Check the script_output.txt file for info about the export. The script will generate some data export files in the current directory, and the script_output.txt file will contain instructions for importing those files. There are 4 csv files to be imported plus a txt file to be inspected. It's a good idea to inspect the csv files as well to make sure that the operations look sane.

## Import files

Before importing any data to DP, it is important to do a backup:

1. Navigate to Utilities -> Backup and Restore
2. Click Create New Backup
3. Click Ok to overwrite the oldest backup

That backup can be restored if things go horribly during the import.

For each of the 4 files, import as directed by the script output. After clicking the Import Records button, you'll want to save the results of the import by clicking All Records -> Export to CSV. The downloaded file can be saved to the ImportResults folder.

## Upload results to Google Drive

Zip up the Upload-Archive directory and upload it to Google Drive for (private) sharing with the rest of the group.
