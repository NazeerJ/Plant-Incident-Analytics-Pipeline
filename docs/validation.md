# Validation and evidence

## Sample evidence

| Check | Expected |
| --- | ---: |
| Plants | 2 |
| Reporting months | 24 |
| Categories | 4 |
| Source rows | 48 |
| Unpivoted fact rows | 192 |
| Total incidents | 296 |

The source-provided notebook execution demonstrated a successful ingestion, matching stage counts, no missing/invalid/duplicate values, reconciliation and archiving. Those saved outputs were removed from the public notebook because they contained source runtime identifiers. This is source-provided execution evidence, not a new Fabric deployment.

## Reproducible local checks

Run `python scripts/validate_project.py` after installing `requirements-dev.txt`. The check:

1. Compiles all Python notebook cells and requires clean outputs/execution metadata.
2. Validates configuration paths, identifiers and category mappings.
3. Checks source grain, dates and counts and reconstructs the expected fact records.
4. Reconciles every fact business field against source and mapping, checks dimension coverage, and verifies the expected counts and total.
5. Decodes and compares the embedded Power Query sample with the reporting workbooks.
6. Verifies PBIP relative model binding, report page/resource references and visual field bindings against the TMDL model.
7. Scans public files and workbook XML for personal source paths and cloud endpoints, and checks that notebook outputs are cleared. A separate packaging scan confirmed that source-company branding is absent.

GitHub Actions runs these checks. Fabric Spark execution and Desktop rendering are separate from these local checks. Desktop/TMDL validation performed during packaging is recorded in [`../validation-results.json`](../validation-results.json); this file describes the packaging run, not a test of every future environment.

## Desktop packaging checks

The standalone PBIP opened in Power BI Desktop. Both the embedded sample and the Excel import path refreshed successfully, with both imported partitions reporting `Ready`. A read-only DAX query returned 192 fact rows, 2 plant rows, 296 total incidents, 5 latest-month incidents and 11 previous-month incidents. The rendered page was inspected for missing data, error icons, clipped labels and generic company branding. The model also passed TMDL deserialisation with 7 tables, 10 measures, 4 relationships and 1 parameter expression.

The installed report-author CLI retains three static catalog errors for the supplied slicers' `dropdown` formatting object and a warning because the visual-container 2.13 schema could not be fetched. These original formatting properties were preserved; the current Desktop installation rendered all three slicers correctly. This is a limitation of the static validation available during packaging, and is recorded separately from the successful Desktop checks.

## Limits

The package does not claim a fresh Fabric run, deployed workspace, scheduled process or production performance test. Use a dedicated Fabric Lakehouse to verify ingestion and recovery in your environment. Power BI requires a refresh after opening because local caches are intentionally omitted.
