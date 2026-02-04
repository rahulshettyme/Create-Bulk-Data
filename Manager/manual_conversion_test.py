
from RS_access_token_generate import get_bearer_token
import openpyxl

def run(data, token, env_config):
    t = get_bearer_token()
    wb = openpyxl.load_workbook('file.xlsx')
    env_sheet = wb['Environment_Details']
    for row in env_sheet.iter_rows(min_row=2):
        print(row)
