{{ config(materialized='view') }}

WITH raw_rh AS (
    SELECT * FROM {{ source('raw_sources', 'rh_employes') }}
)

SELECT
    CAST(TRIM(id_salarie) AS INTEGER) AS id_salarie,
    TRIM(nom) AS nom,
    TRIM(prenom) AS prenom,
    TO_DATE(TRIM(date_naissance), 'DD/MM/YYYY') AS date_naissance,
    TRIM(bu) AS bu,
    TO_DATE(TRIM(date_embauche), 'DD/MM/YYYY') AS date_embauche,
    CAST(REPLACE(TRIM(salaire_brut), ',', '.') AS NUMERIC) AS salaire_brut,
    TRIM(type_contrat) AS type_contrat,
    CAST(CAST(REPLACE(TRIM(nb_jours_cp), ',', '.') AS NUMERIC) AS INTEGER) AS nb_jours_cp,
    TRIM(adresse_domicile) AS adresse_domicile,
    TRIM(moyen_deplacement) AS moyen_deplacement
FROM raw_rh
