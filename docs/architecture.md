# Architecture and engineering decisions

## Configuration

Two workbook sheets control ingestion. `pipeline_config` supplies landing/archive/failed folders, file pattern, source sheet/key columns and four distinct destination tables. `category_mapping` assigns each source incident column a classification and code group.

The notebook rejects duplicate/empty settings, missing keys, overlapping or unsafe file paths, invalid table identifiers and incomplete or duplicate mappings before processing. Mapping the categories separately allows source labels to change without rewriting the unpivot logic.

## Processing stages

1. **Source:** validate worksheet/header structure and remove wholly empty rows.
2. **Bronze:** unpivot the incident columns with Spark SQL `STACK`, write a raw Delta snapshot with source-row/file/run lineage, and check the expected row count. Bronze is overwritten for each input file; it is not a historical append ledger.
3. **Silver:** use temporary Spark views to normalise plant codes, parse first-of-month dates, validate non-negative whole counts and join category mappings. Missing values, invalid values, duplicates and unmapped categories fail the load. No Silver Delta table is persisted.
4. **Gold:** MERGE new plants into the dimension. MERGE facts at `(plant_code, reporting_month, source_category)`, inserting new keys and updating changed business values. Unchanged rows retain their lineage; absent source rows are not deleted.
5. **Reconciliation:** compare validated input with stored facts for the incoming keys using `EXCEPT ALL`, then check for orphan plant keys.
6. **Completion:** move successful files to a run-specific archive directory and complete their audit entry. On failure, attempt a move to the failed-file directory, write failure details and stop the run.

Audit records include stage, status, timestamps, source filename, run identifier, source/Bronze/Silver/fact row counts and error text. Delta table operations commit separately; auditing and file moves do not turn this into a single transaction. Controlled reruns and single-writer operation are the intended recovery model.

## Reporting model

The Power BI Import model contains `dim_plant`, `fact_monthly_incidents`, a calculated calendar and a dedicated measure table. Relationships preserve plant and date filtering. Measures calculate incident totals, same-period prior-year totals and changes, latest/previous-month totals and changes, and factual summary text.

The dashboard retains the supplied report design with a generic company header: totals and change indicators, internal/external incident trends, plant comparisons and a short signal summary. Missing or zero comparison periods are handled by the DAX measures rather than inferred as improvement.

For an immediate local preview, an empty `DataFolder` selects an embedded copy of the reporting sample. Set a directory path to import the two Excel reporting exports instead. Both modes use the same columns and types. The source organisation's SQL connection, workspace metadata and binary data cache are not included.

## Boundaries

This repository supplies a Fabric notebook, not an orchestrated Fabric pipeline item. Scheduling, deployment automation, alerts, concurrent ingestion, Direct Lake, refresh automation and production-scale export are not implemented. The Excel export/import step is explicit and reviewable.
