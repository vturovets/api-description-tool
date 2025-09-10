# api_description_tool/writer_csv.py
import csv

def write_csv(base_filename: str, params: list, req_body: list, res_body: list):
    def write_section(filename, rows):
        if not rows:
            return
        headers = list(rows[0].keys())
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    write_section(f"{base_filename}_params.csv", params)
    write_section(f"{base_filename}_req_body.csv", req_body)
    write_section(f"{base_filename}_res_body.csv", res_body)
