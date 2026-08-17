from flask import Blueprint, request, jsonify

from services.json_importer import importar_relatorio, ImportError_
from routes.dashboard_common import BASE_HEAD, NAVBAR

import_bp = Blueprint("import_bp", __name__)


PAGE_STYLE = """
<style>
    .container-form { max-width: 640px; margin: 20px auto 60px; }
    .card-form { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; font-size: 22px; }
    label { display: block; margin-top: 18px; font-weight: bold; font-size: 14px; }
    input[type=text], input[type=file] { width: 100%; padding: 10px; margin-top: 6px;
        border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; }
    button { margin-top: 24px; width: 100%; padding: 12px; background: #2563eb; color: white;
        border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
    .hint { color: #6b7280; font-size: 13px; margin-top: 4px; }
    .msg { margin-top: 20px; padding: 12px; border-radius: 6px; font-size: 14px; white-space: pre-wrap; }
    .ok { background: #d1fae5; color: #065f46; }
    .erro { background: #fee2e2; color: #991b1b; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #e5e7eb; }
    .status-ok { color: #065f46; font-weight: bold; }
    .status-erro { color: #991b1b; font-weight: bold; }
    .subnav { margin-bottom: 16px; font-size: 13px; }
    .subnav a { color: #2563eb; text-decoration: none; margin-right: 16px; }
</style>
"""

SUBNAV_HTML = (
    '<div class="subnav">'
    '<a href="/jamreport/importar">Importar (nome manual)</a>'
    '<a href="/jamreport/importar/auto">Importar (nome automático)</a>'
    '<a href="/jamreport/importar/lote">Importar em lote</a>'
    '</div>'
)


FORM_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>JAM Report - Importar Simulado</title>
    {head}
    {style}
</head>
<body>
    {navbar}
    <div class="container container-form">
      <div class="card-form">
        {subnav}
        <h1>Importar relatório de Simulado</h1>
        <form method="POST" enctype="multipart/form-data">
            <label>Nome do simulado</label>
            <input type="text" name="nome_simulado" placeholder="Simulado_JAM-19062026" required>
            <div class="hint">Padrão: Simulado_JAM-DDMMAAAA (ou com sufixo de versão, ex: ...2026b)</div>

            <label>Arquivo JSON exportado do AWS Skill Builder</label>
            <input type="file" name="arquivo" accept=".json" required>

            <button type="submit">Importar</button>
        </form>
        {mensagem}
      </div>
    </div>
</body>
</html>
""".replace("{head}", BASE_HEAD).replace("{navbar}", NAVBAR).replace("{style}", PAGE_STYLE).replace("{subnav}", SUBNAV_HTML)


FORM_AUTO_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>JAM Report - Importar (automático)</title>
    {head}
    {style}
</head>
<body>
    {navbar}
    <div class="container container-form">
      <div class="card-form">
        {subnav}
        <h1>Importar relatório (nome automático)</h1>
        <div class="hint">
            A data do simulado é extraída do <strong>nome do arquivo</strong> se ele terminar em
            DDMMAAAA.json (ex: Simulado_JAM-13082026.json). Sem isso, cai no fallback da data de
            geração do relatório na AWS, que pode divergir da data real do simulado — confira o
            selo que aparece no dashboard depois.
        </div>
        <form method="POST" enctype="multipart/form-data">
            <label>Arquivo JSON exportado do AWS Skill Builder</label>
            <input type="file" name="arquivo" accept=".json" required>

            <button type="submit">Importar</button>
        </form>
        {mensagem}
      </div>
    </div>
</body>
</html>
""".replace("{head}", BASE_HEAD).replace("{navbar}", NAVBAR).replace("{style}", PAGE_STYLE).replace("{subnav}", SUBNAV_HTML)


FORM_LOTE_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>JAM Report - Importação em lote</title>
    {head}
    {style}
</head>
<body>
    {navbar}
    <div class="container container-form">
      <div class="card-form">
        {subnav}
        <h1>Importar vários simulados de uma vez</h1>
        <div class="hint">
            Cada arquivo recebe nome e data automáticos: pelo nome do arquivo
            (DDMMAAAA.json) se seguir o padrão, senão pela data de geração do
            relatório na AWS. Se duas datas coincidirem, o segundo recebe
            sufixo "b", o terceiro "c", etc. Um arquivo com problema não
            impede os demais de serem importados.
        </div>
        <form method="POST" enctype="multipart/form-data">
            <label>Arquivos JSON (selecione vários de uma vez)</label>
            <input type="file" name="arquivos" accept=".json" multiple required>

            <button type="submit">Importar todos</button>
        </form>
        {resultado}
      </div>
    </div>
</body>
</html>
""".replace("{head}", BASE_HEAD).replace("{navbar}", NAVBAR).replace("{style}", PAGE_STYLE).replace("{subnav}", SUBNAV_HTML)


# ---------------------------------------------------------------------------
# Upload único, nome manual (comportamento original)
# ---------------------------------------------------------------------------

@import_bp.route("/importar", methods=["GET", "POST"])
def importar():
    if request.method == "GET":
        return FORM_HTML.replace("{mensagem}", "")

    nome_simulado = (request.form.get("nome_simulado") or "").strip()
    arquivo = request.files.get("arquivo")

    if not nome_simulado or not arquivo or arquivo.filename == "":
        msg = '<div class="msg erro">Preencha o nome do simulado e selecione um arquivo.</div>'
        return FORM_HTML.replace("{mensagem}", msg), 400

    try:
        resultado = importar_relatorio(
            raw_bytes=arquivo.read(),
            original_filename=arquivo.filename,
            nome_simulado=nome_simulado,
            user_id=1,  # TODO: trocar pelo usuário autenticado quando existir login
        )
        msg = (
            f'<div class="msg ok">Importado com sucesso!\n'
            f'Simulado: {resultado["nome"]}\n'
            f'JAMs: {resultado["quantidade_jams"]}\n'
            f'Equipes: {resultado["quantidade_equipes"]}</div>'
        )
        return FORM_HTML.replace("{mensagem}", msg)

    except ImportError_ as e:
        msg = f'<div class="msg erro">{e}</div>'
        return FORM_HTML.replace("{mensagem}", msg), 422


# ---------------------------------------------------------------------------
# Upload único, nome automático
# ---------------------------------------------------------------------------

@import_bp.route("/importar/auto", methods=["GET", "POST"])
def importar_auto():
    if request.method == "GET":
        return FORM_AUTO_HTML.replace("{mensagem}", "")

    arquivo = request.files.get("arquivo")
    if not arquivo or arquivo.filename == "":
        msg = '<div class="msg erro">Selecione um arquivo.</div>'
        return FORM_AUTO_HTML.replace("{mensagem}", msg), 400

    try:
        resultado = importar_relatorio(
            raw_bytes=arquivo.read(),
            original_filename=arquivo.filename,
            user_id=1,  # TODO: trocar pelo usuário autenticado quando existir login
        )
        msg = (
            f'<div class="msg ok">Importado com sucesso!\n'
            f'Nome atribuído: {resultado["nome"]}\n'
            f'JAMs: {resultado["quantidade_jams"]}\n'
            f'Equipes: {resultado["quantidade_equipes"]}\n\n'
            f'Confira se a data faz sentido — se não fizer, o nome pode ser '
            f'corrigido depois diretamente no banco.</div>'
        )
        return FORM_AUTO_HTML.replace("{mensagem}", msg)

    except ImportError_ as e:
        msg = f'<div class="msg erro">{e}</div>'
        return FORM_AUTO_HTML.replace("{mensagem}", msg), 422


# ---------------------------------------------------------------------------
# Upload em lote (múltiplos arquivos, todos com nome automático)
# ---------------------------------------------------------------------------

@import_bp.route("/importar/lote", methods=["GET", "POST"])
def importar_lote():
    if request.method == "GET":
        return FORM_LOTE_HTML.replace("{resultado}", "")

    arquivos = request.files.getlist("arquivos")
    arquivos = [a for a in arquivos if a and a.filename]

    if not arquivos:
        msg = '<div class="msg erro">Selecione ao menos um arquivo.</div>'
        return FORM_LOTE_HTML.replace("{resultado}", msg), 400

    linhas = []
    sucesso_count = 0
    erro_count = 0

    for arquivo in arquivos:
        try:
            resultado = importar_relatorio(
                raw_bytes=arquivo.read(),
                original_filename=arquivo.filename,
                user_id=1,  # TODO: trocar pelo usuário autenticado quando existir login
            )
            sucesso_count += 1
            linhas.append(
                f'<tr><td>{arquivo.filename}</td>'
                f'<td class="status-ok">OK</td>'
                f'<td>{resultado["nome"]}</td>'
                f'<td>{resultado["quantidade_jams"]} JAMs / {resultado["quantidade_equipes"]} equipes</td></tr>'
            )
        except ImportError_ as e:
            erro_count += 1
            linhas.append(
                f'<tr><td>{arquivo.filename}</td>'
                f'<td class="status-erro">Erro</td>'
                f'<td colspan="2">{e}</td></tr>'
            )

    resumo = (
        f'<div class="msg {"ok" if erro_count == 0 else "erro"}">'
        f'{sucesso_count} importado(s) com sucesso, {erro_count} com erro.</div>'
        f'<table><tr><th>Arquivo</th><th>Status</th><th>Nome/Detalhe</th><th>Resumo</th></tr>'
        f'{"".join(linhas)}</table>'
    )
    return FORM_LOTE_HTML.replace("{resultado}", resumo)


# ---------------------------------------------------------------------------
# API JSON (para uso futuro por script/dashboard sem formulário HTML)
# ---------------------------------------------------------------------------

@import_bp.route("/importar/api", methods=["POST"])
def importar_api():
    nome_simulado = (request.form.get("nome_simulado") or "").strip() or None
    arquivo = request.files.get("arquivo")

    if not arquivo or arquivo.filename == "":
        return jsonify({"status": "erro", "detalhe": "arquivo é obrigatório"}), 400

    try:
        resultado = importar_relatorio(
            raw_bytes=arquivo.read(),
            original_filename=arquivo.filename,
            nome_simulado=nome_simulado,
            user_id=1,
        )
        return jsonify({"status": "ok", **resultado})
    except ImportError_ as e:
        return jsonify({"status": "erro", "detalhe": str(e)}), 422
