import os
import sys
import json
from datetime import datetime

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'controle-producao-secret-key-2024'

# Configurar CORS para permitir requisições do frontend
CORS(app, origins="*")

# Simulação de banco de dados em memória (para desenvolvimento)
# Em produção, você pode integrar com Firebase ou outro banco
registros_producao = []

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint para verificar se o backend está funcionando"""
    return jsonify({
        'status': 'ok',
        'message': 'Backend do Controle de Produção está funcionando!',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0'
    })

@app.route('/api/salvar-registro', methods=['POST'])
def salvar_registro():
    """Endpoint para salvar registros de produção"""
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({'error': 'Nenhum dado fornecido'}), 400
        
        # Adicionar timestamp e ID único
        registro = {
            'id': len(registros_producao) + 1,
            'timestamp': datetime.now().isoformat(),
            'dados': dados
        }
        
        # Salvar no "banco de dados" em memória
        registros_producao.append(registro)
        
        return jsonify({
            'success': True,
            'message': 'Registro salvo com sucesso!',
            'id': registro['id'],
            'timestamp': registro['timestamp']
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao salvar registro: {str(e)}'
        }), 500

@app.route('/api/listar-registros', methods=['GET'])
def listar_registros():
    """Endpoint para listar todos os registros salvos"""
    try:
        return jsonify({
            'success': True,
            'registros': registros_producao,
            'total': len(registros_producao)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao listar registros: {str(e)}'
        }), 500

@app.route('/api/registro/<int:registro_id>', methods=['GET'])
def obter_registro(registro_id):
    """Endpoint para obter um registro específico por ID"""
    try:
        registro = next((r for r in registros_producao if r['id'] == registro_id), None)
        
        if not registro:
            return jsonify({'error': 'Registro não encontrado'}), 404
            
        return jsonify({
            'success': True,
            'registro': registro
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao obter registro: {str(e)}'
        }), 500

@app.route('/api/estatisticas', methods=['GET'])
def obter_estatisticas():
    """Endpoint para obter estatísticas dos registros"""
    try:
        total_registros = len(registros_producao)
        
        # Calcular estatísticas básicas
        if total_registros > 0:
            ultimo_registro = registros_producao[-1]
            primeiro_registro = registros_producao[0]
        else:
            ultimo_registro = None
            primeiro_registro = None
        
        return jsonify({
            'success': True,
            'estatisticas': {
                'total_registros': total_registros,
                'ultimo_registro': ultimo_registro,
                'primeiro_registro': primeiro_registro,
                'data_consulta': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao obter estatísticas: {str(e)}'
        }), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Servir arquivos estáticos do frontend"""
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return jsonify({
            'message': 'Backend do Controle de Produção',
            'status': 'running',
            'endpoints': [
                '/api/health',
                '/api/salvar-registro',
                '/api/listar-registros',
                '/api/registro/<id>',
                '/api/estatisticas'
            ]
        })

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return jsonify({
                'message': 'Backend do Controle de Produção',
                'status': 'running',
                'version': '2.0.0',
                'endpoints': [
                    '/api/health',
                    '/api/salvar-registro',
                    '/api/listar-registros',
                    '/api/registro/<id>',
                    '/api/estatisticas'
                ]
            })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

