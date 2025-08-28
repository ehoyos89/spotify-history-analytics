# 🎵 Spotify Analytics Pipeline

Un pipeline completo de análisis de datos para procesar y visualizar el historial de reproducción de Spotify utilizando servicios de AWS.

## 📊 Propósito del Proyecto

Este proyecto permite a los usuarios de Spotify obtener insights profundos sobre sus hábitos musicales mediante la recopilación, procesamiento y visualización de datos de su historial de reproducción. El sistema procesa archivos JSONL obtenidos a través de la API de Spotify y genera dashboards interactivos para analizar patrones de escucha.

### ¿Qué Puedes Descubrir?

- 🕐 **Patrones Temporales**: ¿A qué horas y días escuchas más música?
- 🎤 **Top Artistas y Canciones**: Identifica tu contenido más reproducido
- 🔄 **Hábitos de Repetición**: Descubre tus canciones "obsesivas"
- 📅 **Evolución Musical**: Cómo cambian tus gustos a lo largo del tiempo
- 🎭 **Diversidad Musical**: ¿Qué tan variado es tu contenido?
- 📈 **Métricas de Consumo**: Horas totales, artistas únicos, etc.

## 🏗️ Arquitectura del Sistema

```
📱 Spotify API → 📂 S3 (Raw) → 🔍 Glue Crawler → ⚙️ ETL Job → 📂 S3 (Clean) → 🔍 Glue Crawler → 📊 QuickSight
```

### Flujo de Datos Detallado

1. **Recolección**: Extracción de datos via Spotify API → archivos JSONL
2. **Almacenamiento Raw**: Carga de archivos JSONL a S3
3. **Catalogación**: AWS Glue Crawler analiza y cataloga datos raw
4. **Procesamiento**: Job ETL elimina duplicados y optimiza formato (Parquet)
5. **Almacenamiento Limpio**: Datos procesados guardados en S3
6. **Re-catalogación**: Segundo Crawler para datos limpios
7. **Visualización**: QuickSight conecta y genera dashboards interactivos

## 🛠️ Tecnologías Utilizadas

### Servicios AWS Core
- **Amazon S3**: Almacenamiento de datos raw y procesados
- **AWS Glue**: Catalogación de datos y jobs ETL
- **Amazon QuickSight**: Visualización y dashboards

### Lenguajes y Formatos
- **Python/PySpark**: Lógica de procesamiento ETL
- **JSON Lines (JSONL)**: Formato de datos de entrada
- **Apache Parquet**: Formato optimizado para analytics
- **SQL**: Consultas para análisis y visualización

## 📁 Estructura del Proyecto

```
spotify-analytics/
├── data/
│   ├── raw/                    # Archivos JSONL originales
│   └── processed/              # Datos limpios en Parquet
├── glue-jobs/
│   └── deduplication_job.py    # Script PySpark para ETL
├── infrastructure/
│   ├── crawlers/               # Configuraciones de Crawlers
│   └── iam-policies/          # Políticas y roles IAM
├── quicksight/
│   └── dashboard-exports/      # Exports de dashboards
├── docs/
│   ├── setup-guide.md         # Guía de configuración
│   └── data-schema.md         # Documentación del esquema
└── README.md
```

## 🚀 Configuración Inicial

### Prerrequisitos
- Cuenta AWS activa
- Acceso a Spotify API (Client ID y Secret)
- Permisos IAM para servicios AWS utilizados

### 1. Configurar Almacenamiento S3

```bash
# Crear bucket principal
aws s3 mb s3://tu-bucket-spotify

# Crear estructura de carpetas
aws s3api put-object --bucket tu-bucket-spotify --key raw-data/
aws s3api put-object --bucket tu-bucket-spotify --key processed-data/
```

### 2. Configurar IAM Roles

Crear rol `SpotifyAnalyticsRole` con políticas:
- `AWSGlueServiceRole`
- `AmazonS3FullAccess`

### 3. Configurar AWS Glue

**Database:**
```sql
CREATE DATABASE spotify_raw;
CREATE DATABASE spotify_analytics;
```

**Crawlers:**
- `spotify-raw-crawler`: Escanea `s3://tu-bucket/raw-data/`
- `spotify-clean-crawler`: Escanea `s3://tu-bucket/processed-data/`

### 4. Configurar ETL Job

Crear job `spotify-deduplication` con:
- **Tipo**: Spark
- **Lenguaje**: Python 3
- **Workers**: 2 x G.1X
- **Rol IAM**: SpotifyAnalyticsRole

### 5. Configurar QuickSight

- Crear dataset desde Glue Data Catalog
- Importar a SPICE para mejor rendimiento

## 📊 Estructura de Datos

### Formato de Entrada (JSONL)
```json
{
  "track_id": "2wSAWEYUHkt92X4SBAPqZE",
  "name": "Karma Chameleon - Remastered 2002",
  "artist": "Culture Club",
  "played_at": "2025-08-20T22:31:46.306Z",
  "album": "Colour By Numbers",
  "duration_ms": 252773,
  "popularity": 75,
  "explicit": false,
  "artist_id": "6kz53iCdBSqhQCZ21CoLcc",
  "album_id": "51NPMfa9QfxsYtqzcB2VfY",
  "release_date": "1983-10-01",
  "total_tracks": 15,
  "played_date": "2025-08-20",
  "played_hour": "22"
}
```

### Esquema de Tabla Procesada
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `track_id` | string | ID único de la canción |
| `name` | string | Nombre de la canción |
| `artist` | string | Nombre del artista |
| `played_at` | timestamp | Momento exacto de reproducción |
| `duration_ms` | bigint | Duración en milisegundos |
| `popularity` | int | Score de popularidad (0-100) |
| `release_date` | date | Fecha de lanzamiento |


## 💰 Costos Estimados (Mensual)

| Servicio | Uso Típico | Costo Estimado |
|----------|------------|----------------|
| **S3** | 1GB almacenamiento | $0.02 |
| **Glue Crawlers** | 4 ejecuciones/mes | $1.00 |
| **Glue ETL Jobs** | 2 horas/mes | $0.88 |
| **QuickSight** | 1 usuario Standard | $9.00 |
| **SPICE** | 1GB datos | $0.25 |
| **Total** | | **~$16.15/mes** |

## 🔄 Programación y Automatización

### Flujo Semanal Automatizado
```
Domingo 06:00 AM (UTC):
1. Nuevo archivo JSONL → S3
2. Trigger: Lambda function
3. Ejecutar: Raw data crawler
4. Ejecutar: ETL deduplication job
5. Ejecutar: Clean data crawler
6. Refrescar: QuickSight SPICE datasets
7. Enviar: Email report (opcional)
```

### Monitoreo y Alertas
- **Cost Budgets**: Control de gastos AWS

## 📚 Recursos Adicionales

- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api/)
- [AWS Glue ETL Programming Guide](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming.html)
- [QuickSight User Guide](https://docs.aws.amazon.com/quicksight/latest/user/)
- [Apache Parquet Documentation](https://parquet.apache.org/docs/)

## 🔒 Privacidad y Datos

- Los datos de Spotify se mantienen privados en tu cuenta AWS
- No se comparten datos personales con terceros
- Sigue las mejores prácticas de AWS para seguridad de datos


