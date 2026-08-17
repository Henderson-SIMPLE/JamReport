"""Layout e helpers compartilhados entre routes/import_routes.py e routes/dashboard_routes.py."""

BASE_HEAD = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.3/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>
<style>
    body { background: #f4f6f8; color: #1f2937; }
    .navbar-brand { font-weight: bold; }
    .card { border: none; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); margin-bottom: 24px; }
    .stat-value { font-size: 28px; font-weight: bold; }
    .stat-label { color: #6b7280; font-size: 13px; }
    table.table thead { background: #f9fafb; }
    .badge-versao { background: #e0e7ff; color: #3730a3; }
    .badge-confiavel { background: #d1fae5; color: #065f46; }
    .badge-estimada { background: #fef3c7; color: #92400e; }
    .badge-facil { background: #d1fae5; color: #065f46; }
    .badge-medio { background: #fef3c7; color: #92400e; }
    .badge-dificil { background: #fee2e2; color: #991b1b; }
    .badge-sem-avaliacao { background: #e5e7eb; color: #4b5563; }
    .badge-not-started { background: #e5e7eb; color: #4b5563; }
    .badge-started { background: #dbeafe; color: #1e40af; }
    .badge-attempted { background: #fef3c7; color: #92400e; }
    .badge-solved { background: #d1fae5; color: #065f46; }
    .badge-cheating { background: #fee2e2; color: #991b1b; }
    .progress { height: 8px; }
    .taxa-label { font-size: 12px; color: #6b7280; }
    .heat-cell { width: 16px; height: 16px; border-radius: 3px; display: inline-block; margin: 1px; }
    .heat-grid { display: flex; flex-wrap: wrap; gap: 2px; }
    .heat-week { display: flex; flex-direction: column; gap: 2px; }
</style>
"""

NAVBAR = """
<nav class="navbar navbar-dark bg-dark mb-4">
  <div class="container">
    <a class="navbar-brand" href="/jamreport/dashboard">JAM Report</a>
    <div>
      <a class="btn btn-sm btn-outline-light me-2" href="/jamreport/importar/lote">Importar</a>
      <a class="btn btn-sm btn-outline-light me-2" href="/jamreport/dashboard">Dashboard</a>
      <a class="btn btn-sm btn-outline-light me-2" href="/jamreport/dashboard/jams">JAMs</a>
      <a class="btn btn-sm btn-outline-light me-2" href="/jamreport/dashboard/servicos">Serviços AWS</a>
      <a class="btn btn-sm btn-outline-light" href="/jamreport/dashboard/equipes">Equipes</a>
    </div>
  </div>
</nav>
"""


def fmt_segundos(s):
    if s is None:
        return "-"
    s = int(s)
    h, resto = divmod(s, 3600)
    m, seg = divmod(resto, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {seg}s"
    return f"{seg}s"


def fmt_ms(ms):
    if ms is None:
        return "-"
    return fmt_segundos(int(ms) / 1000)


def badge_fonte_data(descricao):
    if not descricao:
        return ""
    if "confiável" in descricao:
        return f'<span class="badge badge-confiavel" title="{descricao}">nome do arquivo</span>'
    if "estimada" in descricao:
        return f'<span class="badge badge-estimada" title="{descricao}">estimada</span>'
    return ""


def barra_taxa(pct, cor="#2563eb"):
    pct = max(0, min(100, pct))
    return f"""
    <div class="progress" title="{pct:.0f}%">
        <div class="progress-bar" role="progressbar" style="width:{pct}%; background:{cor};"></div>
    </div>
    """


def badge_status(status):
    mapa = {
        "NOT_STARTED": ("Não iniciado", "badge-not-started"),
        "STARTED": ("Iniciado", "badge-started"),
        "ATTEMPTED": ("Tentado", "badge-attempted"),
        "SOLVED": ("Resolvido", "badge-solved"),
    }
    label, classe = mapa.get(status, (status, "badge-not-started"))
    return f'<span class="badge {classe}">{label}</span>'


def paginar(itens, page, per_page):
    """Recebe uma lista já pronta e devolve (fatia_da_pagina, total_paginas, page_corrigida)."""
    total = len(itens)
    total_paginas = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_paginas))
    inicio = (page - 1) * per_page
    return itens[inicio:inicio + per_page], total_paginas, page


def controles_paginacao(page, total_paginas, per_page, extra_params: dict):
    """extra_params: outros filtros da URL (ex: {'nome': 'x', 'data_inicio': '2026-01-01'})."""
    if total_paginas <= 1:
        return ""

    def querystring(p, pp=None):
        params = {k: v for k, v in extra_params.items() if v}
        params["page"] = p
        params["per_page"] = pp or per_page
        return "&".join(f"{k}={v}" for k, v in params.items())

    def link(p, texto, ativo=False, desabilitado=False):
        if desabilitado:
            return f'<span class="btn btn-sm btn-outline-secondary disabled">{texto}</span>'
        classe = "btn-primary" if ativo else "btn-outline-secondary"
        return f'<a class="btn btn-sm {classe}" href="?{querystring(p)}">{texto}</a>'

    botoes = [link(page - 1, "&laquo; Anterior", desabilitado=(page <= 1))]
    ultimo_mostrado = 0
    for p in range(1, total_paginas + 1):
        if p == 1 or p == total_paginas or abs(p - page) <= 2:
            botoes.append(link(p, str(p), ativo=(p == page)))
            ultimo_mostrado = p
        elif ultimo_mostrado != -1:
            botoes.append('<span class="px-1">…</span>')
            ultimo_mostrado = -1
    botoes.append(link(page + 1, "Próxima &raquo;", desabilitado=(page >= total_paginas)))

    opcoes_per_page = "".join(
        f'<option value="{n}" {"selected" if n == per_page else ""}>{n}/página</option>'
        for n in [10, 20, 50, 100]
    )
    hidden_inputs = "".join(f'<input type="hidden" name="{k}" value="{v}">' for k, v in extra_params.items() if v)

    seletor_per_page = f"""
    <form method="GET" class="d-inline-block ms-3">
        {hidden_inputs}
        <input type="hidden" name="page" value="1">
        <select name="per_page" class="form-select form-select-sm d-inline-block w-auto" onchange="this.form.submit()">
            {opcoes_per_page}
        </select>
    </form>
    """

    return f'<div class="d-flex align-items-center flex-wrap gap-1 mt-3">{"".join(botoes)}{seletor_per_page}</div>'


def bucket_dificuldade(valor):
    """
    Converte avgChallengeDifficulty (escala 0-5 do AWS Skill Builder, onde
    0 = sem avaliação) em uma faixa aproximada Fácil/Médio/Difícil.
    Isso é uma classificação DERIVADA, a AWS não fornece essa categoria pronta.
    """
    if valor is None or valor == 0:
        return ("sem_avaliacao", "Sem avaliação", "badge-sem-avaliacao")
    if valor <= 2:
        return ("facil", "Fácil", "badge-facil")
    if valor == 3:
        return ("medio", "Médio", "badge-medio")
    return ("dificil", "Difícil", "badge-dificil")
