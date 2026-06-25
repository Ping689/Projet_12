{{ config(materialized='table') }}

WITH rh AS (
    SELECT * FROM {{ ref('stg_rh_employes') }}
),

val AS (
    SELECT * FROM {{ ref('stg_validation_distances') }}
),

act AS (
    SELECT 
        id_salarie, 
        COUNT(*) AS nb_activites 
    FROM {{ ref('stg_activites_sportives') }} 
    GROUP BY id_salarie
),

joined AS (
    SELECT
        rh.id_salarie,
        rh.nom,
        rh.prenom,
        rh.salaire_brut,
        rh.moyen_deplacement,
        COALESCE(val.suspicious, false) AS trajet_suspect,
        
        -- Prime sportive (5% du brut annuel)
        CASE 
            WHEN rh.moyen_deplacement IN ('Vélo/Trottinette/Autres', 'Marche/running') 
                 AND COALESCE(val.suspicious, false) = false 
            THEN true
            ELSE false
        END AS eligible_prime,
        
        -- Nombre d'activités sportives enregistrées
        COALESCE(act.nb_activites, 0) AS nb_activites_sportives
    FROM rh
    LEFT JOIN val ON rh.id_salarie = val.id_salarie
    LEFT JOIN act ON rh.id_salarie = act.id_salarie
)

SELECT
    id_salarie,
    nom,
    prenom,
    salaire_brut,
    moyen_deplacement,
    trajet_suspect,
    eligible_prime,
    
    CASE 
        WHEN eligible_prime = true THEN ROUND(salaire_brut * 0.05, 2)
        ELSE 0.00
    END AS montant_prime,
    
    nb_activites_sportives,
    
    CASE 
        WHEN nb_activites_sportives >= 15 THEN true
        ELSE false
    END AS eligible_jours_bien_etre,
    
    CASE 
        WHEN nb_activites_sportives >= 15 THEN ROUND((salaire_brut / {{ var('working_days_per_year', 251) }}) * 5, 2)
        ELSE 0.00
    END AS cout_jours_bien_etre,
    
    (CASE WHEN eligible_prime = true THEN ROUND(salaire_brut * 0.05, 2) ELSE 0.00 END) +
    (CASE WHEN nb_activites_sportives >= 15 THEN ROUND((salaire_brut / {{ var('working_days_per_year', 251) }}) * 5, 2) ELSE 0.00 END) AS avantage_financier_total

FROM joined
