# Data contract and metric definitions

## Source workbook

File pattern: `monthly_incidents_*.xlsx`. Worksheet: `Sheet1`.

| Column | Meaning |
| --- | --- |
| `Plant` | Plant identifier, standardised to uppercase |
| `Month` | First day of the reporting month |
| `Incidents IC 01/02` | Internal incidents, code group `01/02` |
| `Incidents IC 05/06` | Internal incidents, code group `05/06` |
| `Incidents Ext 01/02` | External incidents, code group `01/02` |
| `Incidents Ext 05/06` | External incidents, code group `05/06` |

Counts must be non-negative whole numbers. Each plant/month/category combination must be unique after unpivoting. Every category requires a unique complete mapping. Code groups are **text**, including their leading zeroes and slash.

## Gold tables and exports

`dbo.dim_plant`: `plant_code` (string), `is_active` (boolean).

`dbo.fact_monthly_incidents` business fields:

| Field | Type | Purpose |
| --- | --- | --- |
| `plant_code` | string | Plant dimension key |
| `reporting_month` | date | First-of-month reporting key |
| `source_category` | string | Source incident-category label |
| `classification` | string | Internal or External |
| `code_group` | string | Mapped group such as `01/02` |
| `incident_count` | BIGINT | Count at the fact grain |

Gold also stores `pipeline_run_id`, `source_file_name`, `source_row_number` and `loaded_at_utc`. The report export contains only the six business fields above. Both reporting workbooks use `sheet1`.

The supplied fact export had Excel date formatting in `code_group`. The repository restores the exact string groups from configuration; counts, plants, dates and category labels are preserved. This prevents spreadsheet autoformatting from changing category semantics.

## Dashboard measures

- **Total incidents:** sum of `incident_count` within the current filters.
- **Prior year:** the selected date period shifted back one year.
- **Year-over-year change:** current total minus prior-year total; percentage change divides by prior-year total. Missing or zero denominators yield blank percentages.
- **Latest month:** the latest fact month under the selected filters.
- **Previous month:** the calendar month immediately before that latest month, even if outside the date selection.
- **Month-over-month change:** latest month minus previous month; percentage divides by the previous-month total. Missing comparison periods remain blank.
- **Overview signal:** factual text about these comparisons; it does not infer causes or claim operational impact.

The sample spans January 2019–December 2020. Relative-to-today calendar flags are preserved from the model and are not evidence of recent sample activity.
