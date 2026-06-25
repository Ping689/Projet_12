{{ config(materialized='view') }}

WITH raw_act AS (
    SELECT * FROM {{ source('raw_sources', 'raw_activites_sportives') }}
)

SELECT
    id,
    CAST(id_salarie AS INTEGER) AS id_salarie,
    CAST(date_debut AS TIMESTAMP) AS date_debut,
    TRIM(sport_type) AS sport_type,
    CAST(distance_m AS INTEGER) AS distance_m,
    CAST(temps_ecoule_s AS INTEGER) AS temps_ecoule_s,
    TRIM(commentaire) AS commentaire
FROM raw_act
