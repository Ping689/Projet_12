{{ config(materialized='view') }}

WITH raw_sport AS (
    SELECT * FROM {{ source('raw_sources', 'raw_sport_employes') }}
)

SELECT
    CAST(TRIM(id_salarie) AS INTEGER) AS id_salarie,
    TRIM(pratique_sport) AS pratique_sport
FROM raw_sport
WHERE id_salarie IS NOT NULL 
  AND TRIM(id_salarie) != ''
  AND pratique_sport IS NOT NULL 
  AND TRIM(pratique_sport) != ''
