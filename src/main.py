"""
Backend Flask simples para o aplicativo Controle de Produção.

Este aplicativo expõe diversos endpoints REST para salvar e recuperar
registros de produção e, principalmente, para gerar relatórios em PDF sob demanda.

O objetivo deste backend é desacoplar o front-end de qualquer
provedor de armazenamento específico. O front-end pode continuar a persistir metadados (por exemplo,
registros de produção) no Firestore ou em outro banco de dados, enquanto delega a geração de PDFs
a este serviço. Como os PDFs são criados sob demanda,
eles não precisam ser armazenados no Firebase Storage. Em vez disso, o back-end compila
o PDF na memória e o envia de volta ao cliente. Caso deseje
persistir PDFs por um longo prazo, você pode modificar o endpoint ``generate_pdf`` para
gravar o arquivo em um repositório de objetos, como Amazon S3, Google Cloud Storage
ou outro serviço de bucket.

O serviço também inclui armazenamento simples na memória para fins de demonstração.
Em produção, você substituiria a lista ``registros_producao``
por chamadas para o banco de dados de sua escolha (por exemplo, Firestore, Postgres, etc.).

Dependências:

* Flask e Flask-CORS para a aplicação web e suporte a origens cruzadas
* reportlab para gerar PDFs (adicione ``reportlab`` ao seu requirements.txt)

Para executar este serviço localmente:

    pip install Flask flask-cors reportlab
    python backend_app.py

O serviço será iniciado em http://localhost:5000. Use uma ferramenta como curl ou
Postman para testar os endpoints.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, UTC
from io import BytesIO
from typing import Dict, List, Any

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask import send_from_directory
import uuid

# Biblioteca de terceiros para geração de PDF. Certifique-se de que ``reportlab`` esteja listado
# no seu ``requirements.txt`` ou ``pyproject.toml`` para que seja instalado
# ao implantar no Render ou em outra plataforma.
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet


app = Flask(__name__)
# Permitir requisições de qualquer origem. Em produção, você pode restringir isso ao
# domínio do seu front-end (por exemplo, https://producao-controle.vercel.app)
CORS(app)

# ---------------------------------------------------------------------------
# Armazenamento na memória (apenas para demonstração)
#
# O front-end pode continuar salvando registros no Firestore. Esta lista existe
# apenas para demonstrar o comportamento da API localmente. Para integrar
# o Firestore neste back-end, você pode instalar ``firebase-admin`` e usar
# métodos do cliente do Firestore no lugar desta lista.
registros_producao: List[Dict[str, Any]] = []

# Diretório onde serão armazenados os PDFs enviados pelo front-end.  Quando o
# servidor inicia, cria automaticamente o diretório se ele não existir.  Em
# ambientes como o Render, o filesystem não é persistente entre deploys,
# portanto esses arquivos são temporários e podem desaparecer quando a instância
# é reiniciada. Se você precisar de armazenamento permanente, considere
# integrar com um serviço de armazenamento (S3, GCS, etc.).
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/api/health", methods=["GET"])
def health() -> Any:
    """Simple health check to verify the service is running."""
    return jsonify({
        "status": "ok",
        "message": "Backend Controle de Produção está em execução.",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0"
    })


@app.route("/api/salvar-registro", methods=["POST"])
def salvar_registro() -> Any:
    """
    Salvar um registro de produção.

    O front-end deve enviar um payload JSON com todos os dados de produção relevantes
    (operador, registro de data e hora, silos, observações, etc.). Este
    endpoint atribui um ID inteiro simples e armazena o registro na memória.

    Em uma implantação real, você persistiria ``dados`` no Firestore ou em um
    banco de dados relacional aqui. O ID retornado pode ser usado posteriormente para buscar
    metadados ou gerar PDFs sob demanda.
    """
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({"success": False, "error": "Nenhum dado fornecido"}), 400

    # Atribua um ID inteiro exclusivo com base no tamanho atual da lista. Em um
    # cenário de armazenamento persistente, você pode usar um UUID.
    registro_id = len(registros_producao) + 1
    registro = {
        "id": registro_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "dados": dados,
    }
    registros_producao.append(registro)

    return jsonify({
        "success": True,
        "message": "Registro salvo com sucesso!",
        "id": registro_id,
        "timestamp": registro["timestamp"],
    }), 201


@app.route("/api/listar-registros", methods=["GET"])
def listar_registros() -> Any:
    """Retornar todos os registros de produção salvos."""
    return jsonify({
        "success": True,
        "registros": registros_producao,
        "total": len(registros_producao)
    })


@app.route("/api/registro/<int:registro_id>", methods=["GET"])
def obter_registro(registro_id: int) -> Any:
    """Retornar um registro específico pelo seu ID inteiro."""
    registro = next((r for r in registros_producao if r["id"] == registro_id), None)
    if registro is None:
        return jsonify({"success": False, "error": "Registro não encontrado"}), 404
    return jsonify({"success": True, "registro": registro})


def _build_pdf_elements(dados: Dict[str, Any]) -> List[Any]:
    """
    Constrói uma lista de elementos (Flowables) do ReportLab/Platypus para um
    relatório de produção. Esta função organiza as informações do registro de
    produção em seções bem definidas, utilizando tabelas e parágrafos para
    aproximar o layout utilizado no front-end.  Se novas seções precisarem
    ser incluídas, basta acrescentar novos elementos à lista.

    :param dados: Dicionário contendo todos os dados do registro de produção.
    :return: Lista de Flowables a ser utilizada pelo ``SimpleDocTemplate``.
    """
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    heading_style = styles["Heading4"]
    heading_style.fontSize = 12
    heading_style.leading = 14
    heading_style.spaceAfter = 6

    elements: List[Any] = []

    # Título principal
    title = Paragraph("<b>Controle Diário da Britagem / Moagem</b>", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Informações básicas do operador e turno
    info_rows = []
    # Campos e rótulos correspondentes
    campos_info = [
        ("operador", "Operador(es)"),
        ("visto", "Visto"),
        ("hp", "HP"),
        ("turno", "Turno"),
        ("data", "Data"),
        ("horasExtras", "Horas Extras")
    ]
    for chave, rotulo in campos_info:
        valor = dados.get(chave)
        if valor:
            # Formata a data no padrão brasileiro se o campo for data
            if chave == "data":
                try:
                    valor = datetime.fromisoformat(valor).strftime("%d/%m/%Y")
                except Exception:
                    pass
            info_rows.append([rotulo, str(valor)])

    if info_rows:
        info_table = Table(info_rows, colWidths=[130, 350])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 12))

    # Estoque de Produto
    silos = dados.get('silos') or []
    if silos:
        elements.append(Paragraph('Estoque de Produto', heading_style))
        silos_data = [['Silo', 'Estoque (t)', 'Horas Trabalhadas']]
        for silo in silos:
            silos_data.append([
                silo.get('nome', ''),
                silo.get('estoque', ''),
                silo.get('horasTrabalhadas', '')
            ])
        silos_table = Table(silos_data, colWidths=[230, 100, 100])
        silos_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
        ]))
        elements.append(silos_table)
        elements.append(Spacer(1, 12))

    # Paradas operacionais
    paradas = dados.get('paradas') or []
    if paradas:
        elements.append(Paragraph('Paradas Operacionais', heading_style))
        paradas_data = [['Início', 'Fim', 'Motivo', 'Duração', 'Observação']]
        for p in paradas:
            paradas_data.append([
                p.get('inicio', ''),
                p.get('fim', ''),
                p.get('motivo', ''),
                p.get('duracao', ''),
                p.get('observacao', '')
            ])
        paradas_table = Table(paradas_data, colWidths=[70, 70, 150, 60, 110])
        paradas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
        ]))
        elements.append(paradas_table)
        elements.append(Spacer(1, 12))

    # Distribuição de Paradas (agrupamento por motivo e porcentagem)
    if paradas:
        # Cálculo dos tempos e percentuais
        total_minutes = 0
        motivos: Dict[str, int] = {}
        for p in paradas:
            dur = p.get('duracao', '00:00')
            try:
                h, m = [int(x) for x in dur.split(':')]
                minutes = h * 60 + m
            except Exception:
                minutes = 0
            total_minutes += minutes
            mot = p.get('motivo', 'Sem motivo') or 'Sem motivo'
            motivos[mot] = motivos.get(mot, 0) + minutes
        if total_minutes > 0:
            distrib_data = [['Motivo', 'Tempo', '%']]
            for mot, mins in motivos.items():
                hrs = mins // 60
                mins_rem = mins % 60
                tempo_str = f"{hrs:02d}:{mins_rem:02d}"
                perc = (mins / total_minutes) * 100
                distrib_data.append([mot, tempo_str, f"{perc:.2f}%"])
            elements.append(Paragraph('Distribuição de Paradas', heading_style))
            distrib_table = Table(distrib_data, colWidths=[200, 70, 70])
            distrib_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
            ]))
            elements.append(distrib_table)
            elements.append(Spacer(1, 12))

    # Resumo Operacional
    tempo_efetivo = dados.get('tempoEfetivo') or '00:00'
    producao_total = dados.get('toneladas') or dados.get('producaoTotal') or ''
    resumo = dados.get('resumoParadas') or {}
    total_paradas = resumo.get('totalParadas') if isinstance(resumo, dict) else None
    tempo_total_paradas = resumo.get('tempoTotalParadas') if isinstance(resumo, dict) else None
    if total_paradas is None:
        total_paradas = len(paradas)
    if tempo_total_paradas is None:
        # calcula tempo total de paradas
        total_minutes = sum([
            (int(p.get('duracao', '00:00').split(':')[0]) * 60 + int(p.get('duracao', '00:00').split(':')[1]))
            if p.get('duracao') else 0 for p in paradas
        ])
        hrs = total_minutes // 60
        mins_rem = total_minutes % 60
        tempo_total_paradas = f"{hrs:02d}:{mins_rem:02d}"

    producao_por_hora = dados.get('producaoPorHora')
    if not producao_por_hora and producao_total and tempo_efetivo:
        try:
            pt = float(producao_total) if isinstance(producao_total, (int, float, str)) else 0
            h, m = [int(x) for x in tempo_efetivo.split(':')]
            total_h = h + (m / 60)
            producao_por_hora = f"{pt / total_h:.2f}" if total_h > 0 else '0.00'
        except Exception:
            producao_por_hora = '0.00'

    resumo_data = [['Tempo Efetivo', 'Produção Total (t)', 'Total de Paradas (Tempo)', 'Produção/Hora']]
    resumo_data.append([
        tempo_efetivo,
        str(producao_total) if producao_total != '' else '-',
        f"{total_paradas} ({tempo_total_paradas})",
        producao_por_hora if producao_por_hora else '-'
    ])
    elements.append(Paragraph('Resumo Operacional', heading_style))
    resumo_table = Table(resumo_data, colWidths=[120, 140, 160, 100])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
    ]))
    elements.append(resumo_table)
    elements.append(Spacer(1, 12))

    # Observações
    obs_text = dados.get('observacoes') or dados.get('observacoes/atuações')
    if obs_text:
        elements.append(Paragraph('Observações / Atuações no Processo', heading_style))
        elements.append(Paragraph(str(obs_text), normal_style))
        elements.append(Spacer(1, 12))

    # Checklist de Equipamentos
    checklist = dados.get('checklist') or []
    if checklist:
        elements.append(Paragraph('Checklist de Equipamentos', heading_style))
        checklist_data = [['Equipamento', 'Situação', 'Observação']]
        for item in checklist:
            checklist_data.append([
                item.get('equipamento', ''),
                item.get('situacao', ''),
                item.get('observacao', '')
            ])
        checklist_table = Table(checklist_data, colWidths=[200, 100, 200])
        checklist_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
        ]))
        elements.append(checklist_table)
        elements.append(Spacer(1, 12))

    return elements


@app.route("/api/generate-pdf", methods=["POST"])
def gerar_pdf() -> Any:
    """
    Gere um relatório em PDF a partir dos dados JSON publicados.

    O cliente deve enviar um corpo JSON idêntico ao registro armazenado no
    Firestore (ou qualquer outro formato usado pelo seu front-end). Este endpoint
    constrói um PDF dinamicamente usando o reportlab e o transmite de volta
    na resposta. O arquivo não é persistido no servidor.

    Retorna uma resposta de arquivo com ``Content-Type: application/pdf`` e
    cabeçalhos de disposição de conteúdo apropriados.
    """
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({"success": False, "error": "Nenhum dado fornecido"}), 400

    # Utilize SimpleDocTemplate para construir um PDF com layout mais elaborado
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=36, leftMargin=36,
                            topMargin=36, bottomMargin=36)
    # Constrói os elementos de layout para o relatório
    elementos = _build_pdf_elements(dados)
    try:
        doc.build(elementos)
    except Exception as build_err:
        # Em caso de erro na construção, registra e retorna erro ao cliente
        print(f"Erro ao construir PDF: {build_err}")
        return jsonify({"success": False, "error": "Erro ao construir PDF"}), 500
    buffer.seek(0)

    filename = f"relatorio_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
    return send_file(buffer,
                     as_attachment=True,
                     download_name=filename,
                     mimetype="application/pdf")

# ---------------------------------------------------------------------------
# Endpoint para receber PDFs gerados pelo front-end e disponibilizá-los via URL
#
# Este endpoint espera que o cliente envie um arquivo PDF usando multipart/form-data
# com o campo de formulário chamado ``file``. Ele atribui um nome único ao arquivo
# usando uuid4, salva o conteúdo no diretório UPLOAD_FOLDER e retorna um JSON
# contendo a URL pública onde o arquivo pode ser baixado.  Note que o
# armazenamento no disco local é temporário em plataformas como o Render,
# portanto arquivos podem ser removidos quando a instância for reiniciada. Para
# persistência duradoura, integre com um serviço de armazenamento externo.
@app.route("/api/upload-pdf", methods=["POST"])
def upload_pdf() -> Any:
    """
    Recebe um PDF via formulário multipart e retorna uma URL para acesso.

    O cliente deve enviar o arquivo PDF no campo ``file`` de um objeto
    ``FormData``. O servidor salva o arquivo no diretório ``uploads`` com um
    nome único baseado em UUID e responde com uma URL que pode ser usada para
    baixar o PDF.  Se nenhum arquivo for enviado ou o campo estiver vazio,
    retorna um erro 400.
    """
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "Nenhum arquivo enviado"}), 400
    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return jsonify({"success": False, "error": "Nome de arquivo inválido"}), 400

    # Gera um nome único com base em UUID preservando a extensão original
    ext = os.path.splitext(uploaded_file.filename)[1] or '.pdf'
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    try:
        uploaded_file.save(save_path)
    except Exception as save_err:
        print(f"Erro ao salvar arquivo: {save_err}")
        return jsonify({"success": False, "error": "Erro ao salvar arquivo"}), 500

    # Constrói a URL pública para o arquivo salvo. ``request.url_root`` inclui
    # o esquema e domínio (e termina com ``/``), mas removemos qualquer
    # barra extra para evitar ``//`` na URL resultante.
    base_url = request.url_root.rstrip('/')
    file_url = f"{base_url}/uploads/{unique_name}"

    return jsonify({"success": True, "url": file_url}), 201


# Rota auxiliar para servir os PDFs salvos em ``UPLOAD_FOLDER``
#
# O front-end pode acessar o arquivo diretamente via ``/uploads/<nome>``.  O
# argumento ``as_attachment=True`` força o navegador a baixar o arquivo em vez de
# tentar abri-lo inline, mas isso pode ser ajustado conforme sua necessidade.
@app.route("/uploads/<path:filename>", methods=["GET"])
def uploaded_file(filename: str) -> Any:
    """
    Serve arquivos PDF que foram enviados e armazenados no servidor.

    Este endpoint é usado internamente para disponibilizar os arquivos enviados
    pelo endpoint ``/api/upload-pdf``.  Não há qualquer controle de acesso aqui;
    em uma aplicação real você pode adicionar autenticação ou verificar
    permissões antes de servir o arquivo.
    """
    try:
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404


if __name__ == "__main__":
    # Ao executar localmente (por exemplo, ``python backend_app.py``), isso iniciará
    # o servidor de desenvolvimento. Em produção, use um servidor WSGI como o gunicorn.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))