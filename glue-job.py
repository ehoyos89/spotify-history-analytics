# Importaciones necesarias para un job de AWS Glue con PySpark.
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame

# --- INICIALIZACIÓN DEL ENTORNO DE GLUE Y SPARK ---

# Obtiene los argumentos pasados al job de Glue, como el nombre del job.
args = getResolvedOptions(sys.argv, ['JOB_NAME'])

# Crea un SparkContext, que es el punto de entrada para cualquier funcionalidad de Spark.
sc = SparkContext()
# Crea un GlueContext, que es una envoltura sobre el SparkContext y proporciona funcionalidades específicas de Glue.
glueContext = GlueContext(sc)
# Obtiene la SparkSession del GlueContext para poder trabajar con DataFrames.
spark = glueContext.spark_session
# Crea un objeto Job para gestionar el ciclo de vida del job de Glue.
job = Job(glueContext)
# Inicializa el job con su nombre y argumentos.
job.init(args['JOB_NAME'], args)

# --- PARÁMETROS DE CONFIGURACIÓN DEL JOB ---
# Es importante que actualices estas variables con los nombres correctos de tus recursos en AWS.

# Nombre de la base de datos en el Catálogo de Datos de Glue donde se encuentra la tabla original.
DATABASE_NAME = "spotify_analytics"
# Nombre de la tabla en el Catálogo de Datos que contiene el historial de Spotify.
TABLE_NAME = "historial"
# Ruta en S3 donde se guardarán los datos limpios y sin duplicados.
OUTPUT_PATH = "s3://spotify-historial-raw/historial-limpio/"
# (Opcional) Nombre para una nueva base de datos si decides catalogar los datos limpios.
CLEAN_DATABASE_NAME = "analytics-database"
# (Opcional) Nombre para la nueva tabla de datos limpios.
CLEAN_TABLE_NAME = "historial_limpio"
# Columna utilizada para identificar y eliminar registros duplicados. 'played_at' es ideal porque es único para cada reproducción.
DEDUP_COLUMN = "played_at"

# --- EJECUCIÓN DEL JOB ---

print(f"Iniciando job de deduplicación para la tabla '{TABLE_NAME}'...")

# 1. CARGAR DATOS DESDE EL CATÁLOGO DE DATOS DE GLUE
print(f"Cargando datos desde la base de datos '{DATABASE_NAME}' y tabla '{TABLE_NAME}'...")
try:
    # Crea un DynamicFrame a partir de la tabla especificada en el Catálogo de Datos.
    # Un DynamicFrame es similar a un DataFrame de Spark pero puede manejar esquemas de datos que cambian.
    source_data = glueContext.create_dynamic_frame.from_catalog(
        database=DATABASE_NAME,
        table_name=TABLE_NAME
    )
    print("✓ Datos cargados exitosamente desde el catálogo.")
except Exception as e:
    # Captura y muestra un error si la tabla o la base de datos no se encuentran.
    print(f"✗ Error al acceder a la tabla: {str(e)}")
    print("Asegúrate de que los nombres de DATABASE_NAME y TABLE_NAME sean correctos.")
    raise e

print(f"Número de registros originales: {source_data.count()}")

# 2. ELIMINAR DUPLICADOS
# Para usar funciones más avanzadas como la eliminación de duplicados, es conveniente convertir el DynamicFrame a un DataFrame de Spark.
print("Convirtiendo a DataFrame de Spark para eliminar duplicados...")
df = source_data.toDF()

print(f"Eliminando duplicados basados en la columna '{DEDUP_COLUMN}'...")
# El método `dropDuplicates` de un DataFrame elimina las filas que tienen valores idénticos en la columna especificada.
deduplicated_df = df.dropDuplicates([DEDUP_COLUMN])

# Una vez procesado, se convierte de nuevo a un DynamicFrame para usar las funcionalidades de escritura de Glue.
deduplicated_data = DynamicFrame.fromDF(deduplicated_df, glueContext, "deduplicated_data")

print(f"Número de registros después de la deduplicación: {deduplicated_data.count()}")

# (Opcional) Muestra el esquema de los datos para verificar que las columnas y tipos son correctos.
print("Esquema de los datos limpios:")
deduplicated_data.printSchema()

# 3. GUARDAR LOS DATOS LIMPIOS EN S3
print(f"Guardando datos limpios en formato Parquet en la ruta: {OUTPUT_PATH}")
# Escribe el DynamicFrame resultante en S3.
glueContext.write_dynamic_frame.from_options(
    frame=deduplicated_data,
    connection_type="s3",
    connection_options={
        "path": OUTPUT_PATH,
        # (Opcional) Se pueden definir claves de partición para organizar los datos, por ejemplo, por año o mes.
        "partitionKeys": []
    },
    # Se elige el formato Parquet porque es columnar, comprimido y optimizado para análisis con herramientas como Athena y QuickSight.
    format="parquet",
    # Contexto de transformación para el bookmarking del job de Glue.
    transformation_ctx="write_parquet_data"
)

print("✓ Datos limpios guardados exitosamente en S3.")
print("Puedes crear un nuevo crawler de Glue apuntando a la ruta de salida para catalogar estos datos y usarlos en Athena o QuickSight.")

# --- FINALIZACIÓN DEL JOB ---
print("Job completado exitosamente.")
# Confirma que el job ha terminado su ejecución, permitiendo a Glue registrar el estado y los bookmarks.
job.commit()
