from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/api/generate-and-upload-pdf', methods=['POST'])
def generate_and_upload_pdf():
    try:
        data = request.json
        # Nome único para o PDF
        filename = f"{uuid.uuid4().hex}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # Criar PDF simples
        c = canvas.Canvas(filepath, pagesize=letter)
        c.drawString(100, 750, f"Relatório de Produção - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        if isinstance(data, dict):
            for idx, (key, value) in enumerate(data.items()):
                c.drawString(100, 730 - (idx * 20), f"{key}: {value}")
        c.save()

        file_url = request.url_root.rstrip('/') + '/uploads/' + filename
        return jsonify({"success": True, "url": file_url}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
