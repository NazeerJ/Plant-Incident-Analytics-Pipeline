"""Validate the portable project without requiring Fabric or Power BI Desktop."""
from __future__ import annotations

import base64
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
import re
import zipfile
import zlib

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
NAME = "Plant Incident Analytics"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(path, sheet=None):
    workbook = openpyxl.load_workbook(ROOT / path, read_only=True, data_only=True)
    try:
        worksheet = workbook[sheet] if sheet else workbook.active
        values = list(worksheet.values)
        require(bool(values), f"Empty worksheet: {path}")
        require(len(set(values[0])) == len(values[0]), f"Duplicate headers: {path}")
        return [dict(zip(values[0], row)) for row in values[1:] if any(v is not None for v in row)]
    finally:
        workbook.close()


def month(value):
    if isinstance(value, datetime):
        result = value.date()
    elif isinstance(value, date):
        result = value
    else:
        result = datetime.fromisoformat(str(value)).date()
    require(result.day == 1, f"Month must start on day one: {value}")
    return result.isoformat()


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def validate():
    config_path = "configuration/incident_pipeline_config.xlsx"
    setting_rows = rows(config_path, "pipeline_config")
    config = {r["setting"]: r["value"] for r in setting_rows}
    require(len(config) == len(setting_rows), "Duplicate configuration keys")
    keys = {"source_folder", "archive_folder", "failed_folder", "file_pattern", "sheet_name", "plant_column", "month_column", "audit_table", "bronze_table", "plant_table", "fact_table"}
    require(keys <= config.keys() and all(config[k] for k in keys), "Missing configuration values")
    folders = [config[k].rstrip("/") for k in ("source_folder", "archive_folder", "failed_folder")]
    for folder in folders:
        require(folder.startswith("Files/") and "\\" not in folder and not {"", ".", ".."} & set(folder.split("/")), "Unsafe processing folder")
    for i, folder in enumerate(folders):
        for other in folders[i + 1:]:
            require(folder != other and not folder.startswith(other + "/") and not other.startswith(folder + "/"), "Overlapping processing folders")
    tables = [config[k] for k in ("audit_table", "bronze_table", "plant_table", "fact_table")]
    require(len({t.lower() for t in tables}) == 4, "Destination tables must differ")
    require(all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", t) for t in tables), "Invalid table name")
    require(config["plant_column"] != config["month_column"], "Source key column names must differ")
    mapping_rows = rows(config_path, "category_mapping")
    mapping = {r["source_category"]: (r["classification"], r["code_group"]) for r in mapping_rows}
    require(len(mapping) == len(mapping_rows) and bool(mapping), "Duplicate or absent mappings")
    require(all(all(isinstance(v, str) and v.strip() for v in (key, *values)) for key, values in mapping.items()), "Invalid category mappings")

    source_files = sorted((ROOT / "data/source").glob(config["file_pattern"]))
    require(len(source_files) == 1, "Expected one demonstration source workbook")
    source = rows(source_files[0].relative_to(ROOT), config["sheet_name"])
    categories = set(source[0]) - {config["plant_column"], config["month_column"]}
    require(categories == set(mapping), "Category headers and mappings differ")
    expected = []
    for record in source:
        plant = str(record[config["plant_column"]]).strip().upper()
        require(bool(plant) and plant != "NONE", "Missing plant")
        for category in categories:
            count = record[category]
            require(isinstance(count, (int, float)) and not isinstance(count, bool) and count >= 0 and int(count) == count, "Invalid incident count")
            classification, group = mapping[category]
            expected.append((plant, month(record[config["month_column"]]), category, classification, group, int(count)))
    require(len({r[:3] for r in expected}) == len(expected), "Duplicate source fact keys")
    facts = rows("data/reporting/fact_monthly_incidents.xlsx", "sheet1")
    actual = []
    for r in facts:
        require(isinstance(r["code_group"], str), "Code groups must remain text")
        actual.append((r["plant_code"], month(r["reporting_month"]), r["source_category"], r["classification"], r["code_group"], r["incident_count"]))
    require(Counter(actual) == Counter(expected), "Source-to-fact reconciliation failed")
    plants = rows("data/reporting/dim_plant.xlsx", "sheet1")
    require(len({r["plant_code"] for r in plants}) == len(plants), "Duplicate plant keys")
    require(all(isinstance(r["is_active"], bool) for r in plants), "Plant active flags must be boolean")
    require({r[0] for r in actual} == {r["plant_code"] for r in plants}, "Plant dimension does not cover sample facts")
    require((len(source), len(actual), len(plants), len({r[1] for r in actual}), len(categories), sum(r[5] for r in actual)) == (48, 192, 2, 24, 4, 296), "Unexpected demonstration counts")

    notebook = json.loads((ROOT / "notebooks/incident_ingest.ipynb").read_text(encoding="utf-8"))
    require("synapse_widget" not in notebook.get("metadata", {}), "Notebook contains saved runtime state")
    code_cells = 0
    cell_ids = [cell.get("id") for cell in notebook["cells"]]
    require(all(isinstance(cell_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cell_id) for cell_id in cell_ids) and len(set(cell_ids)) == len(cell_ids), "Invalid or duplicate notebook cell IDs")
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            require(cell.get("outputs") == [] and cell.get("execution_count") is None, "Notebook outputs are not cleared")
            compile("".join(cell["source"]), f"notebook-cell-{index}", "exec")
            code_cells += 1

    project = ROOT / "powerbi"
    pbip = json.loads((project / f"{NAME}.pbip").read_text(encoding="utf-8"))
    report = project / pbip["artifacts"][0]["report"]["path"]
    binding = json.loads((report / "definition.pbir").read_text(encoding="utf-8"))
    require(set(binding["datasetReference"]) == {"byPath"}, "Report has an external model connection")
    model = (report / binding["datasetReference"]["byPath"]["path"]).resolve()
    require(model.is_relative_to(ROOT.resolve()) and (model / "definition.pbism").is_file(), "Missing local semantic model")
    for table, workbook in (("dim_plant", "dim_plant.xlsx"), ("fact_monthly_incidents", "fact_monthly_incidents.xlsx")):
        definition = (model / f"definition/tables/{table}.tmdl").read_text(encoding="utf-8")
        compressed = re.search(r'Binary\.FromText\("([A-Za-z0-9+/=]+)"', definition)
        require(compressed is not None, f"Missing embedded sample for {table}")
        embedded = json.loads(zlib.decompress(base64.b64decode(compressed[1]), -15))
        reference = rows(f"data/reporting/{workbook}", "sheet1")
        reference_values = [[v.isoformat() if isinstance(v, (date, datetime)) else v for v in row.values()] for row in reference]
        require(embedded == reference_values, f"Embedded sample differs from {workbook}")

    schema = {}
    for file in (model / "definition/tables").glob("*.tmdl"):
        definition = file.read_text(encoding="utf-8")
        fields = set()
        for match in re.finditer(r"^\t(?:column|measure) (.+?)(?: =.*)?$", definition, re.M):
            name = match[1].strip()
            if name.startswith("'") and name.endswith("'"):
                name = name[1:-1].replace("''", "'")
            fields.add(name)
        schema[file.stem] = fields
    pages = json.loads((report / "definition/pages/pages.json").read_text(encoding="utf-8"))
    require(len(pages["pageOrder"]) == 1, "Unexpected report page count")
    for page in pages["pageOrder"]:
        require((report / f"definition/pages/{page}/page.json").is_file(), "Missing report page")
    visual_count = 0
    for file in (report / "definition").rglob("*.json"):
        definition = json.loads(file.read_text(encoding="utf-8"))
        if file.name == "visual.json":
            visual_count += 1
        for node in walk(definition):
            for kind in ("Measure", "Column"):
                field = node.get(kind)
                if not isinstance(field, dict):
                    continue
                entity = field.get("Expression", {}).get("SourceRef", {}).get("Entity")
                if entity is not None:
                    require(entity in schema and field.get("Property") in schema[entity], f"Unknown report field: {entity}.{field.get('Property')}")
            package = node.get("ResourcePackageItem")
            if isinstance(package, dict) and "ItemName" in package:
                require((report / "StaticResources" / package["PackageName"] / package["ItemName"]).is_file(), "Missing visual resource")
    require(visual_count > 0, "No report visuals")

    forbidden_paths = re.compile(r"[A-Z]:[\\/](?:Users|Morea|Nazeer)|datawarehouse\.fabric\.microsoft\.com|semanticmodelid=", re.I)
    for file in ROOT.rglob("*"):
        if not file.is_file() or any(part in {".git", ".pbi", "__pycache__", ".venv"} for part in file.parts):
            continue
        if file == Path(__file__).resolve():
            continue
        if file.suffix == ".xlsx":
            with zipfile.ZipFile(file) as workbook:
                texts = [workbook.read(name).decode("utf-8") for name in workbook.namelist() if name.endswith(".xml")]
        elif file.suffix in {".md", ".json", ".ipynb", ".tmdl", ".pbip", ".pbir", ".pbism", ".svg", ".py", ".yml"}:
            texts = [file.read_text(encoding="utf-8")]
        else:
            continue
        require(all(not forbidden_paths.search(text) for text in texts), f"Private connection/path found: {file.relative_to(ROOT)}")

    return {"status": "passed", "source_rows": len(source), "fact_rows": len(actual), "plants": len(plants), "months": 24, "categories": 4, "total_incidents": 296, "notebook_code_cells_compiled": code_cells, "report_pages": len(pages["pageOrder"]), "report_visuals": visual_count, "embedded_sample_reconciled": True}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
