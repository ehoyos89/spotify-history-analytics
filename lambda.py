# Importaciones de librerías estándar y de AWS/Spotify.
import boto3  # SDK de AWS para Python.
import spotipy  # Librería para interactuar con la API de Spotify.
from spotipy.oauth2 import SpotifyOAuth  # Manejo de autenticación OAuth2 con Spotify.
import os  # Funciones para interactuar con el sistema operativo.
import shutil  # Operaciones de alto nivel con archivos, como copiar.
import time  # Funciones relacionadas con el tiempo.
import json  # Para trabajar con datos en formato JSON.
from datetime import datetime  # Para manejar fechas y horas.

# --- INICIALIZACIÓN DE CLIENTES DE AWS ---
# Se inicializan fuera del handler para reutilizar las conexiones en ejecuciones consecutivas de la Lambda.
s3 = boto3.client('s3')  # Cliente para interactuar con S3.
ssm = boto3.client('ssm')  # Cliente para interactuar con AWS Systems Manager Parameter Store.

# --- FUNCIÓN PRINCIPAL DE LA LAMBDA ---
def lambda_handler(event, context):
    """
    Punto de entrada para la ejecución de la función Lambda.
    Esta función se encarga de:
    1. Gestionar el caché de autenticación de Spotify.
    2. Obtener credenciales seguras desde AWS Parameter Store.
    3. Autenticarse con la API de Spotify.
    4. Obtener las canciones reproducidas recientemente.
    5. Guardar los datos en S3 en dos formatos: JSONL para Glue y JSON estándar.
    """
    # Ruta del archivo de caché de Spotipy en el paquete de la Lambda.
    packaged_cache_path = "./.cache"
    # Ruta temporal donde la Lambda puede escribir. El directorio /tmp es el único lugar con permisos de escritura.
    tmp_cache_path = "/tmp/.cache"
    
    # Si el caché no existe en /tmp pero sí en el paquete, se copia.
    # Esto es crucial para persistir el token de refresco de Spotify entre ejecuciones.
    if not os.path.exists(tmp_cache_path) and os.path.exists(packaged_cache_path):
        print(f"Copiando archivo de caché desde {packaged_cache_path} a {tmp_cache_path}...")
        shutil.copy(packaged_cache_path, tmp_cache_path)

    # 1. OBTENER CONFIGURACIÓN DESDE VARIABLES DE ENTORNO
    try:
        # Ruta en Parameter Store donde se guardan los secretos de Spotify.
        parameter_path = os.environ['PARAMETER_PATH']
        # Nombre del bucket de S3 donde se guardarán los datos.
        s3_bucket = os.environ['S3_BUCKET']
    except KeyError as e:
        print(f"❌ Error: La variable de entorno {e} no está configurada.")
        raise

    # 2. OBTENER SECRETOS DESDE PARAMETER STORE
    try:
        # Obtiene todos los parámetros bajo la ruta especificada. `WithDecryption=True` es para parámetros de tipo SecureString.
        response = ssm.get_parameters_by_path(Path=parameter_path, WithDecryption=True)
        # Convierte la lista de parámetros en un diccionario más fácil de usar.
        secrets = {param['Name'].split('/')[-1]: param['Value'] for param in response['Parameters']}
        # Valida que todos los secretos necesarios estén presentes.
        if not all(k in secrets for k in ["client-id", "client-secret", "redirect-uri"]):
             raise ValueError("Faltan secretos (client-id, client-secret, o redirect-uri) en Parameter Store.")
    except Exception as e:
        print(f"❌ Error obteniendo secretos de Parameter Store: {e}")
        raise

    # 3. AUTENTICARSE CON SPOTIFY
    # Crea una instancia de Spotipy con el gestor de autenticación OAuth.
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=secrets["client-id"],
        client_secret=secrets["client-secret"],
        redirect_uri=secrets["redirect-uri"],
        scope="user-read-recently-played",  # Permiso para leer las canciones reproducidas recientemente.
        cache_path=tmp_cache_path,  # Usa la ruta en /tmp para leer y escribir el caché.
        open_browser=False  # Impide que intente abrir un navegador para autenticar.
    ))

    # 4. OBTENER Y PROCESAR CANCIONES
    tracks = get_recent_tracks(sp)
    
    if tracks:
        print(f"Se obtuvieron {len(tracks)} canciones. Guardando en S3...")
        # Guarda los datos en formato JSONL, ideal para AWS Glue.
        glue_url = save_json_for_glue(tracks, s3_bucket)
        # Guarda una copia en formato JSON estándar, más legible para humanos.
        regular_url = save_regular_json(tracks, s3_bucket)
        
        if glue_url and regular_url:
            print("🎉 Proceso completado exitosamente.")
            return {'statusCode': 200, 'body': json.dumps('Datos guardados correctamente en S3.')}
    
    print("No se encontraron nuevas canciones o hubo un error al guardar en S3.")
    return {'statusCode': 200, 'body': json.dumps('No se procesaron nuevas canciones.')}

def get_recent_tracks(sp_client):
    """Obtiene las últimas 50 canciones reproducidas desde la API de Spotify."""
    all_tracks = []
    target_count = 50  # La API de Spotify permite un máximo de 50 por petición.
    print(f"Obteniendo las últimas {target_count} canciones de Spotify...")
    
    try:
        # Llama al endpoint de la API para obtener las canciones reproducidas recientemente.
        results = sp_client.current_user_recently_played(limit=target_count)
        items = results.get('items', [])
        
        if not items:
            print("No se encontraron canciones en el historial reciente.")
            return []

        # Itera sobre cada canción y extrae los campos de interés.
        for item in items:
            track_data = {
                'track_id': item['track']['id'],
                'name': item['track']['name'],
                'artist': item['track']['artists'][0]['name'],
                'played_at': item['played_at'],
                'album': item['track']['album']['name'],
                'duration_ms': item['track']['duration_ms'],
                'popularity': item['track']['popularity'],
                'explicit': item['track']['explicit'],
                'artist_id': item['track']['artists'][0]['id'],
                'album_id': item['track']['album']['id'],
                'release_date': item['track']['album']['release_date'],
                'total_tracks': item['track']['album']['total_tracks'],
                'played_date': item['played_at'][:10],  # Extrae solo la fecha.
                'played_hour': item['played_at'][11:13], # Extrae solo la hora.
                'collection_timestamp': datetime.now().isoformat()  # Añade un timestamp de cuándo se recogió el dato.
            }
            all_tracks.append(track_data)
            
        print(f"Se extrajeron datos de {len(all_tracks)} canciones.")
        return all_tracks

    except Exception as e:
        print(f"❌ Error en la petición a la API de Spotify: {e}")
        return []

def _upload_string_to_s3(content_string, bucket_name, key):
    """Función auxiliar para subir un string a un objeto en S3."""
    try:
        s3.put_object(Bucket=bucket_name, Key=key, Body=content_string.encode('utf-8'))
        return True
    except Exception as e:
        print(f"❌ Error subiendo archivo a S3 (s3://{bucket_name}/{key}): {e}")
        return False

def save_json_for_glue(tracks, bucket_name, file_prefix='raw/historial'):
    """
    Guarda los datos en formato JSON Lines (JSONL), donde cada línea es un objeto JSON.
    Este formato es óptimo para ser procesado por AWS Glue.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Crea una estructura de partición por fecha para organizar los datos en S3.
    date_partition = datetime.now().strftime("year=%Y/month=%m/day=%d")
    file_name = f'{file_prefix}/{date_partition}/historial_{timestamp}.jsonl'
    # Convierte la lista de diccionarios a un string en formato JSONL.
    jsonl_content = "\n".join(json.dumps(track, ensure_ascii=False) for track in tracks)
    s3_url = f's3://{bucket_name}/{file_name}'
    
    if _upload_string_to_s3(jsonl_content, bucket_name, file_name):
        print(f"✅ Archivo JSONL para Glue guardado en: {s3_url}")
        return s3_url
    return None

def save_regular_json(tracks, bucket_name, file_prefix='processed/historial'):
    """
    Guarda los datos en un formato JSON estándar, indentado para ser fácilmente legible por humanos.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f'{file_prefix}/historial_{timestamp}.json'
    # Convierte la lista de diccionarios a un string JSON formateado.
    json_content = json.dumps(tracks, ensure_ascii=False, indent=2)
    s3_url = f's3://{bucket_name}/{file_name}'

    if _upload_string_to_s3(json_content, bucket_name, file_name):
        print(f"✅ Archivo JSON regular guardado en: {s3_url}")
        return s3_url
    return None
