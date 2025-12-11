import whisper 
import os # Importar os para manejo de rutas 

# Definir la ruta del archivo de audio de prueba 
# Asegúrate de que este archivo exista en tu carpeta tmp/ 
AUDIO_TEST_PATH = "tmp/test_loquendo.mp3" # O tmp/test_audio.wav, o el que descargues 

# Crear la carpeta tmp si no existe 
os.makedirs("tmp", exist_ok=True) 

# Si no tienes un archivo de prueba, puedes crearlo (solo para propósitos de prueba de Whisper) 
# Por ejemplo, descarga uno y colócalo en tmp/test_audio.mp3 

print("🧠 Probando Whisper...") 
try: 
    model = whisper.load_model("tiny") 
    print("✅ WHISPER TINY FUNCIONA!") 

    # Advertencia de FP16 es normal en CPU, no te preocupes por ella. 

    if not os.path.exists(AUDIO_TEST_PATH): 
        print(f"❌ ERROR: No se encontró el archivo de audio de prueba: {AUDIO_TEST_PATH}") 
        print("Por favor, coloca un archivo de audio (mp3, wav, webm) en la carpeta tmp/ y renómbralo a 'test_audio.mp3' (o el nombre que uses).") 
        # Salir si no hay archivo de prueba para evitar el error de FFmpeg 
        exit()  

    # Intenta transcribir el archivo de prueba 
    result = model.transcribe(AUDIO_TEST_PATH, language='es', fp16=False) # fp16=False para evitar la advertencia 
    print(f"✅ TEXTO TRANSCRITO: '{result['text']}'") 
    print("🎉 ¡Whisper funciona correctamente con un archivo de audio existente!") 
except Exception as e: 
    print(f"❌ ERROR GENERAL DURANTE LA TRANSCRIPCIÓN: {e}") 
    import traceback 
    print(traceback.format_exc())