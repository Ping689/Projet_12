import os
import json
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, trim, coalesce, lit, round, when
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType
BASE_DIR = Path(__file__).resolve().parents[1]
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

postgres_host = os.getenv("POSTGRES_HOST", "localhost")
if postgres_host == "localhost" or postgres_host == "127.0.0.1":
    postgres_host = "host.docker.internal"

prime_pct = float(os.getenv("SPORT_PRIME_PCT", "0.05"))

OUTPUTS_DIR = BASE_DIR / "outputs"
delta_raw_path = str(OUTPUTS_DIR / "delta_raw_activities")
delta_finance_path = str(OUTPUTS_DIR / "delta_finance")

# Schéma du message Debezium (CDC) pour les insertions/updates dans PostgreSQL
debezium_schema = StructType([
    StructField("payload", StructType([
        StructField("op", StringType(), True),
        StructField("after", StructType([
            StructField("id_salarie", StringType(), True),
            StructField("sport_type", StringType(), True),
            StructField("distance_m", StringType(), True),
            StructField("temps_ecoule_s", StringType(), True),
            StructField("date_debut", StringType(), True)
        ]), True)
    ]), True)
])

# Configuration de la connexion JDBC vers PostgreSQL
jdbc_url = f"jdbc:postgresql://{postgres_host}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'sport_data_solution')}"
jdbc_options = {
    "url": jdbc_url,
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "3178"),
    "driver": "org.postgresql.Driver"
}

def process_batch(batch_df, batch_id):
    if batch_df.count() == 0:
        return

    print(f"Traitement du batch {batch_id}...")

    # Extraire et nettoyer les données
    valid_activities = batch_df \
        .filter(col("op").isin("r", "c", "u") & col("id_salarie").isNotNull()) \
        .select(
            trim(col("id_salarie")).alias("id_salarie"),
            col("sport_type"),
            col("distance_m").cast("double").alias("distance_m"),
            col("temps_ecoule_s").cast("double").alias("temps_ecoule_s"),
            col("date_debut")
        )

    if valid_activities.count() == 0:
        print(f"Aucune nouvelle activité valide dans le batch {batch_id}.")
        return

    # Gérer la persistence dans delta_raw_activities
    delta_log_exists = os.path.exists(os.path.join(delta_raw_path, "_delta_log"))
    if not delta_log_exists:
        valid_activities.write.format("delta").mode("overwrite").save(delta_raw_path)
        all_activities = valid_activities
    else:
        valid_activities.write.format("delta").mode("append").save(delta_raw_path)
        all_activities = spark.read.format("delta").load(delta_raw_path)

    print(f"Nombre total d'activités sportives chargées en Delta : {all_activities.count()}")

    # Agréger le nombre d'activités par salarié
    act_agg = all_activities.groupBy("id_salarie").count().withColumnRenamed("count", "nb_activites_sportives")

    # Charger les référentiels RH et Distances depuis PostgreSQL
    rh_df = spark.read.format("jdbc").options(**jdbc_options).option("dbtable", "rh_employes").load()
    val_df = spark.read.format("jdbc").options(**jdbc_options).option("dbtable", "validation_distances").load()

    # Nettoyer les clés de jointure des référentiels
    rh_clean = rh_df.withColumn("id_salarie", trim(col("id_salarie")))
    val_clean = val_df.withColumn("id_salarie", trim(col("id_salarie"))).withColumn("suspicious", coalesce(col("suspicious"), lit(False)))
    act_clean = act_agg.withColumn("id_salarie", trim(col("id_salarie")))

    # Effectuer les jointures
    joined = rh_clean \
        .join(val_clean, "id_salarie", "left") \
        .join(act_clean, "id_salarie", "left")

    # Coalesce des valeurs vides
    joined = joined \
        .withColumn("suspicious", coalesce(col("suspicious"), lit(False))) \
        .withColumn("nb_activites_sportives", coalesce(col("nb_activites_sportives"), lit(0)))

    # Calcul de l'éligibilité et du montant de la prime sportive (5% du brut)
    joined = joined.withColumn(
        "eligible_prime",
        when(
            (col("moyen_deplacement").isin("Vélo/Trottinette/Autres", "Marche/running")) & 
            (col("suspicious") == False),
            True
        ).otherwise(False)
    ).withColumn(
        "montant_prime",
        when(col("eligible_prime") == True, round(col("salaire_brut") * lit(prime_pct), 2)).otherwise(0.00)
    )

    # Calcul de l'éligibilité et du coût des Jours Bien-être (5 jours de repos)
    working_days = int(os.getenv("WORKING_DAYS_PER_YEAR", "251"))
    joined = joined.withColumn(
        "eligible_jours_bien_etre",
        when(col("nb_activites_sportives") >= 15, True).otherwise(False)
    ).withColumn(
        "cout_jours_bien_etre",
        when(col("eligible_jours_bien_etre") == True, round((col("salaire_brut") / working_days) * 5, 2)).otherwise(0.00)
    )

    # Avantage financier total
    joined = joined.withColumn(
        "avantage_financier_total",
        round(col("montant_prime") + col("cout_jours_bien_etre"), 2)
    )

    # Sélection des colonnes finales
    final_df = joined.select(
        "id_salarie",
        "nom",
        "prenom",
        col("salaire_brut").cast(DoubleType()),
        "moyen_deplacement",
        col("suspicious").alias("trajet_suspect"),
        "eligible_prime",
        "montant_prime",
        col("nb_activites_sportives").cast(IntegerType()),
        "eligible_jours_bien_etre",
        "cout_jours_bien_etre",
        "avantage_financier_total"
    )

    # Écriture dans la table Delta Lake finale
    final_df.write.format("delta").mode("overwrite").save(delta_finance_path)
    print(f"Table Delta Lake financière mise à jour dans : {delta_finance_path}")

def main():
    global spark
    print("Démarrage de la session Spark avec Delta Lake...")
    
    # Configurer Delta et les dépendances Maven (JDBC et Kafka)
    builder = SparkSession.builder \
        .appName("Projet12_SparkStreaming") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.jars.packages", "org.postgresql:postgresql:42.6.0,io.delta:delta-spark_2.12:3.0.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
        .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true")

    spark = builder.getOrCreate()
    print("Spark connecté avec succès !")

    # Initialisation de la lecture en streaming depuis Redpanda
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Abonnement au topic Redpanda postgres.public.activites_sportives ({kafka_bootstrap})...")
    df_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", kafka_bootstrap) \
        .option("subscribe", "postgres.public.activites_sportives") \
        .option("startingOffsets", "earliest") \
        .load()

    # Parser la charge utile JSON issue du Debezium CDC
    parsed_stream = df_stream \
        .selectExpr("CAST(value AS STRING) as json_str") \
        .select(from_json(col("json_str"), debezium_schema).alias("data")) \
        .select("data.payload.op", "data.payload.after.*")

    # Démarrer l'écriture en continu avec foreachBatch
    query = parsed_stream.writeStream \
        .foreachBatch(process_batch) \
        .option("checkpointLocation", str(OUTPUTS_DIR / "checkpoint_finance")) \
        .start()

    print("Stream d'ingestion et transformation démarré en tâche de fond...")
    query.awaitTermination()

if __name__ == "__main__":
    main()
