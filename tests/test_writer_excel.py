from pathlib import Path
import openpyxl

from api_description_tool.writer_excel import write_excel


def test_write_excel_creates_sheets_and_headers(tmp_path):
    xlsx = tmp_path / "out.xlsx"
    params = [{"Name": "x", "Mandatory": True, "Expected Value(s)": "string", "In": "header", "Description": "", "Examples": ""}]
    req = [{"Path": "", "Property": "name", "Mandatory": True, "Expected Value(s)": "string", "Description": "", "Examples": ""}]
    res = [{"Status": "200", "Path": "", "Property": "id", "Mandatory": True, "Expected Value(s)": "integer", "Description": "", "Examples": ""}]

    write_excel(str(xlsx), params, req, res)

    assert xlsx.exists()
    wb = openpyxl.load_workbook(str(xlsx))
    assert wb.sheetnames == ["Params", "Req Body", "Res Body"]
    ws_params = wb["Params"]
    headers = [cell.value for cell in ws_params[1]]
    assert headers[:4] == ["Name", "Mandatory", "Expected Value(s)", "In"]