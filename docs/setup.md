# Setup and reporting handoff

## 1. Preview the Power BI report locally

1. Extract or clone the complete repository. Keep the `.pbip`, `.Report` and `.SemanticModel` folders together.
2. In a current Power BI Desktop installation, open `powerbi/Plant Incident Analytics.pbip`. Enable PBIP/enhanced PBIR support in Desktop settings if required, and reopen Desktop.
3. Select **Refresh**. No imported-data cache is shipped; Desktop materialises the embedded generic sample on refresh.
4. Check the Plant Overview page. Its all-data incident total is 296. The saved page selection may show a narrower year or plant selection; clear slicers to inspect all data.
5. To read workbooks, use **Transform data → Manage parameters**, set `DataFolder` to the absolute directory containing `dim_plant.xlsx` and `fact_monthly_incidents.xlsx`, then apply and refresh. Both sheets must be named `sheet1`. An empty parameter uses the embedded sample.

Save a PBIX from Desktop if you need a single-file distribution. The editable PBIP is supplied here for source review.

## 2. Prepare Microsoft Fabric

Use a Fabric workspace with capacity that supports notebooks and Lakehouses, permission to create/write items, and a schema-enabled Lakehouse. Attach that Lakehouse to the imported notebook as its **default Lakehouse**.

The notebook requires Fabric's `spark` and `notebookutils` environment, plus `pandas` and an Excel engine such as `openpyxl`. The local validation requirements are separate; install or attach these Excel packages in your Fabric environment if unavailable. Do not run the ingestion notebook as a standalone local Python script.

Upload:

| Repository file | Default Lakehouse location |
| --- | --- |
| `configuration/incident_pipeline_config.xlsx` | `Files/configuration/incident_pipeline_config.xlsx` |
| `data/source/monthly_incidents_201901_202012.xlsx` | `Files/data/monthly_incidents_201901_202012.xlsx` |

Import `notebooks/incident_ingest.ipynb`. The first code cell reads the configuration from the mounted `/lakehouse/default/Files/configuration/` path. Review configuration values before running; use dedicated project tables and folders. The notebook creates missing schemas and tables, rather than replacing existing schemas.

## 3. Run and inspect

Run cells in order. The notebook validates configuration, creates the audit/Bronze/Gold tables, defines transformation and loading functions, and processes matching files sequentially. The source pattern is `monthly_incidents_*.xlsx`; Excel lock files beginning with `~$` are ignored.

Expected first sample load:

- 48 source rows × 4 incident columns = 192 Bronze rows and 192 validated fact rows.
- 2 plant dimension rows and 296 total incidents.
- An audit entry with `SUCCESS`, stage/count details and a completed timestamp.
- The source moved from `Files/data/` to `Files/archive/<run-id>/`.

Inspect `dbo.pipeline_audit`, `dbo.dim_plant` and `dbo.fact_monthly_incidents`. The final audit-query cell uses the configured audit table. On an empty landing folder, processing records `SKIPPED`.

## 4. Feed the report

The final notebook cell exports `dim_plant.xlsx` and `fact_monthly_incidents.xlsx` to `Files/reporting/`. Download both files into the same local directory, set Power BI's `DataFolder` to that directory, and refresh.

This export is designed for the small portfolio dataset: it collects selected Gold columns to pandas on the notebook driver. For larger datasets, design and test a scalable lakehouse connection separately. This repository contains neither a Fabric Data Factory orchestration definition nor an automatic export/refresh schedule.

## 5. Correct and rerun

Read the audit stage and error. Correct the workbook or mapping, then move the intended input back to `Files/data/` from its archive or failed-file folder before rerunning. Preserve the original archived copy for traceability. New keys are inserted and changed values updated; unchanged rows are retained and omitted keys are not deleted.

Use one notebook writer at a time. A failure may occur after a merge has committed; the whole process is not atomic. Always inspect/reconcile target tables before assuming a failed run changed nothing. Archive and export failures require investigation even if the Gold merge succeeded.
