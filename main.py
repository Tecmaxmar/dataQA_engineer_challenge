import os
import pandas as pd
from datetime import datetime
import re
import numpy as np
import variables

################################################################

source = variables.source_folder
destination = variables.destination
desc_fields = variables.desc_fields
not_null_fields = variables.not_null_fields
areas = variables.areas
file_freshness = variables.file_freshness

file_report_header = 'file;total_rows;null_rows;bad_phone_rows;bad_correctness_rows;bad_uniqueness_rows;is_fresh;\n'
# I have many different regex for different kind of phone validations
#International phone regex
#rgx_phone = re.compile(r'\(?\+[0-9]{1,3}\)? ?-?[0-9]{1,3} ?-?[0-9]{3,5} ?-?[0-9]{4}( ?-?[0-9]{3})? ?(\w{1,10}\s?\d{1,6})?')
#Simple phone regex
rgx_phone = re.compile('\+?\d[\d -]{8,12}\d')
#India format phone regex
#rgx_phone = re.compile(r'^(?:(?:\+|0{0,2})91(\s*[\ -]\s*)?|[0]?)?[789]\d{9}|(\d[ -]?){10}\d$')


################################################################

## Check functions ##

#The Date validated here is the actual date of the file, not the name of the file
#This date represents when the file was uploaded into the repository
def check_date(file):
    file_date = datetime.fromtimestamp(os.path.getctime(source + file)).date()
    now = datetime.now().date()
    if file_date == now:
        return("OK")
    else:
        return("ERR")

def check_format(file):
    if os.path.splitext(source +file)[1].lower() == ".csv":
        return ("OK")
    else:
        return ("ERR")

def check_size(file):
    if os.stat(source+file).st_size > 0:
        return ("OK")
    else:
        return ("ERR")

def special_clean(x):
    x2= re.sub('[^ A-Za-záéíóúÁÉÍÓÚÜü0-9]', "", x)
    return x2

def clean_records(data):
    for field in desc_fields:
        data[field] = data[field].map(lambda x: special_clean(x))
        return(data)

def check_nulls(data):
    null_result=''
    null_rows =[]
    for n_field in not_null_fields:
        null_rows = [*null_rows,  *np.where(  (data[n_field].isna()) | (data[n_field].str=='') )[0] ]
        null_result = null_result + 'Null_' + n_field+ ';'+ str(np.where(  (data[n_field].isna()) | (data[n_field].str=='') )[0]) + ';\n'
    null_rows = list(set(null_rows))
    return(null_result, null_rows)

def check_phone(data):
    bad_phone_rows=[]
    data[['phone1','phone2']] = data['phone'].str.split('\r\n', n=2 , expand=True)
    data['phone1'] = data['phone1'].str.strip()
    data['phone2'] = data['phone2'].str.strip()
    phone_results = 'not_valid_phone1;'+ str(np.where(data['phone1'].str.contains(rgx_phone)== False)[0]) + ';\n'
    phone_results = phone_results + 'not_valid_phone2;' + str(np.where( (data['phone2'].str.contains(rgx_phone) == False) & (data['phone2'].str != None ) & (data['phone2'].str != '' ))[0]) + ';\n'
    bad_phone_rows = [*bad_phone_rows, *np.where(data['phone1'].str.contains(rgx_phone)== False)[0], *np.where( (data['phone2'].str.contains(rgx_phone) == False) & (data['phone2'].str != None ) & (data['phone2'].str != ' ' ) )[0]]
    bad_phone_rows = list(set(bad_phone_rows))
    data['phone1'] = data['phone1'].str.replace('+','')
    data['phone2'] = data['phone2'].str.replace('+', '')
    return(phone_results, data, bad_phone_rows)

def check_correctness(data, areas):
    correct_results = 'incorrect_location;' + str(np.where(data['location'].isin(areas) == False)[0]) + ';\n'
    bad_rows = np.where(data['location'].isin(areas) == False)[0]
    return (correct_results, bad_rows)

def get_areas():
    areas_data = pd.read_excel(source +areas)
    return(areas_data['Area'].to_list())

def check_uniqueness(data):
    unique_results = 'duplicated_records;' + str(np.where(data.duplicated() == True)[0]) + ';\n'
    bad_rows = np.where(data.duplicated() == True)[0]
    return (unique_results, bad_rows)

# The freshness is measured on the name of the file using the parameter 'file_freshness'
def check_freshness(file):
    fresh_results= 'fresh_file'
    file_date = datetime.strptime(file[10:18], '%Y%m%d').date()
    now = datetime.now().date()
    if (now-file_date).days > file_freshness:
        fresh_results = 'not_fresh_file'
    return(fresh_results)

def validate_quality(file, areas):

    data = pd.read_csv(source+file, header=0)
    total_rows = (len(data.index))
    data = clean_records(data)
    null_report, null_rows = check_nulls(data)
    phone_report, data, bad_phone_rows = check_phone(data)
    correct_report, bad_correctness_rows = check_correctness(data, areas)
    # Uniqueness or Identifiability: The rows must be unique on the same file. Duplicates are wrong
    unique_report, bad_uniqueness_rows = check_uniqueness(data)
    # Currency-Freshness : The file must be acceptably up to date.
    # We assume that the file is new on the repository but maybe is old
    fresh_file_report = check_freshness(file)
    # Compile row and File report
    row_report = null_report+phone_report+correct_report+unique_report
    file_report = file + ';'+str(total_rows) + ';'+ str(len(null_rows))+ ';'+ str(len(bad_phone_rows))+ ';'+ str(len(bad_correctness_rows))+';'+str(len(bad_uniqueness_rows))+';'+ fresh_file_report+';\n'
    bad_rows = [*null_rows, *bad_phone_rows, *bad_correctness_rows, *bad_uniqueness_rows]
    bad_rows= list(set(bad_rows))
    bad_data = data.loc[bad_rows]
    good_data = data.drop(bad_rows)
    return(row_report, file_report, bad_data,good_data )

################################################################
## Input and export functions ##

# Get a list of the files to process. Bad files goes to the bad_list
def get_files_list():
    good_list = []
    bad_list = ''
    files = os.listdir(source)
    for file in files:
        chk_date = check_date(file)
        if chk_date != "OK":
            bad_list = bad_list + 'outdated_file;'+ file + ';\n'
        chk_format = check_format(file)
        if chk_format != "OK":
            bad_list = bad_list + 'bad_format_file;'+ file + ';\n'
        chk_size= check_size(file)
        if chk_size != "OK":
            bad_list = bad_list + 'empty_file;'+ file + ';\n'
        if chk_date == chk_format == chk_size == "OK":
            good_list.append(file)
    return(good_list, bad_list)

def good_output(file,good_data):
    file = file.replace('.csv', '.out')
    good_data.to_csv(destination+file)

def bad_output(file, bad_data, row_result):
    file = file.replace('.csv', '.bad')
    bad_data.to_csv(destination+file)
    metadata = "metadata_" + file
    with open(destination+metadata, 'w') as f:
        f.write(row_result)

def final_report(file_report, bad_files):
    now = datetime.now().date()
    with open(destination+'process_result_'+ str(now)+'.out', 'w') as g:
        g.write(file_report)
    with open(destination+'ignored_files_'+ str(now)+'.bad', 'w') as h:
        h.write(bad_files)

################################################################
## Main function ##

if __name__ == '__main__':
    file_report = file_report_header
    areas = get_areas()
    file_list, bad_files = get_files_list()
    for file in file_list:
        row_result, file_result, bad_data, good_data = validate_quality(file, areas)
        good_output(file,good_data)
        bad_output(file, bad_data, row_result)
        file_report = file_report + file_result
    final_report(file_report, bad_files)

