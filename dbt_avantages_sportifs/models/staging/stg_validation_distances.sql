{{ config(materialized='view') }}

WITH raw_val AS (
    SELECT * FROM {{ source('raw_sources', 'raw_validation_distances') }}
)

SELECT
    CAST(id_salarie AS INTEGER) AS id_salarie,
    CAST(distance_km AS NUMERIC) AS distance_km,
    TRIM(status) AS status,
    TRIM(mode) AS mode,
    CAST(suspicious AS BOOLEAN) AS suspicious
FROM raw_val
