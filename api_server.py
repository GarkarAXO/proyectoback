from flask import Flask, request, jsonify
import threading
import sys
import os

# Añadir el directorio del proyecto al path para importar main_orchestrator
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main_orchestrator import main_orchestrator

app = Flask(__name__)

@app.route('/run_scraper', methods=['POST'])
def run_scraper():
    # Ejecutar main_orchestrator en un hilo separado para no bloquear la respuesta HTTP
    thread = threading.Thread(target=main_orchestrator)
    thread.start()
    return jsonify({"message": "Scraper iniciado en segundo plano."}), 202

if __name__ == '__main__':
    # Asegurarse de que el entorno virtual esté activado si se ejecuta directamente
    # Esto es más para desarrollo local, en producción se usaría un WSGI server
    if 'VIRTUAL_ENV' not in os.environ:
        print("Advertencia: No se detectó un entorno virtual activo. Asegúrate de activarlo.")
    
    app.run(host='0.0.0.0', port=5000)
