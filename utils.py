import csv
import datetime
import sys

TODAY_STR = datetime.date.today().strftime('%m/%d/%Y')


def validate_headers(filename, expected, actual):
    expected_set = set(expected)
    actual_set = set(actual)
    missing_list = list(expected_set.difference(actual_set))
    if len(missing_list) > 0:
        print("Missing expected header(s) in %s: %s" % (filename, missing_list))
        sys.exit(1)
    extra_list = list(actual_set.difference(expected_set))
    if len(extra_list) > 0:
        print("Found unexpected header(s) in %s: %s" % (filename, extra_list))
        sys.exit(1)


def load_csv_file(filename, expected_headers):
    if not filename.endswith('.csv'):
        print("%s must be a csv file" % (filename))
        sys.exit(1)
    res = []
    with open(filename, 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        validate_headers(filename, expected_headers, reader.fieldnames)
        for row in reader:
            res.append(row)
    print("    %s: Number of input records read = %d" % (filename, len(res)))
    return res


def save_as_csv_file(filename, header_fields, data):
    with open(filename, 'w') as outputfile:
        writer = csv.DictWriter(outputfile, header_fields)
        writer.writeheader()
        for record in data:
            writer.writerow(record)
    print("    %s: Number of output records for upload = %d" % (filename, len(data)))


def save_as_text_file(filename, messages):
    with open(filename, 'w') as outputfile:
        for message in messages:
            outputfile.write(message)
    print("    %s: Number of output messages = %d" % (filename, len(messages)))


def modified_fields(old_dict, new_dict):
    fields = []

    removed_keys = set(old_dict.keys()).difference(new_dict.keys())
    if len(removed_keys) > 0:
        raise ValueError('Keys in old dict but not new dict: %s' % str(removed_keys))

    added_keys = set(new_dict.keys()).difference(old_dict.keys())
    if len(added_keys) > 0:
        raise ValueError('Keys in new dict but not old dict: %s' % str(added_keys))

    for key in old_dict.keys():
        if old_dict[key] != new_dict[key]:
            fields.append(key)
    return fields


def list_with_mods(l, add=[], remove=[]):
    res = l + add
    for v in remove:
        res.remove(v)
    return res


def dict_filtered_copy(dict_to_copy, keys_to_copy):
    res = {}
    for key in keys_to_copy:
        if key in dict_to_copy:
            res[key] = dict_to_copy[key]
    return res

def normalize_email(email):
    return email.lower().strip()
