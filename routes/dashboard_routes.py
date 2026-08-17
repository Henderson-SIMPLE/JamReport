import calendar as calendar_mod
import json
from datetime import timedelta

from flask import Blueprint, request, abort
from sqlalchemy import func

from database import db
from models import (
    Simulado, SimuladoTeam, Team, Challenge, ChallengeMetric,
    TeamChallengeResult, SimuladoChallenge, AwsService, ChallengeService,
)
from routes.dashboard_common import (
    BASE_HEAD, NAVBAR, fmt_segundos, fmt_ms, badge_fonte_data, barra_taxa, bucket_dificuldade,
    badge_status, paginar, controles_paginacao,
)

dashboard_bp = Blueprint("dashboard_bp", __name__)


# ---------------------------------------------------------------------------
# Visão geral (com filtros + mapa de calor)
# ---------------------------------------------------------------------------

@dashboard_bp.route("/dashboard")
def dashboard_overview():
    nome_filtro = (request.args.get("nome") or "").strip()
    data_inicio = (request.args.get("data_inicio") or "").strip()
    data_fim = (request.args.get("data_fim") or "").strip()
    equipe_id = request.args.get("equipe_id", type=int)

    query = Simulado.query
    if nome_filtro:
        query = query.filter(Simulado.nome.ilike(f"%{nome_filtro}%"))
    if data_inicio:
        query = query.filter(Simulado.data_simulado >= data_inicio)
    if data_fim:
        query = query.filter(Simulado.data_simulado <= data_fim)
    if equipe_id:
        ids_simulados_da_equipe = [
            r[0] for r in db.session.query(SimuladoTeam.simulado_id).filter_by(team_id=equipe_id).all()
        ]
        query = query.filter(Simulado.id.in_(ids_simulados_da_equipe))

    simulados = query.order_by(Simulado.data_simulado.desc(), Simulado.versao).all()
    todas_equipes = Team.query.order_by(Team.name).all()

    linhas = []
    total_equipes_geral = 0
    total_jams_geral = 0
    total_solved_geral = 0
    total_possiveis_geral = 0
    contagem_por_dia = {}  # date -> {"simulados": n, "solved": n, "possiveis": n}

    for s in simulados:
        n_equipes = SimuladoTeam.query.filter_by(simulado_id=s.id).count()
        media_score = db.session.query(func.avg(SimuladoTeam.final_score)).filter_by(simulado_id=s.id).scalar()
        total_solved = db.session.query(func.sum(SimuladoTeam.number_challenges_solved)).filter_by(simulado_id=s.id).scalar() or 0

        possiveis = (s.quantidade_jams or 0) * n_equipes
        taxa = (total_solved / possiveis * 100) if possiveis else 0

        total_equipes_geral += n_equipes
        total_jams_geral += s.quantidade_jams or 0
        total_solved_geral += total_solved
        total_possiveis_geral += possiveis

        if s.data_simulado:
            dia = contagem_por_dia.setdefault(s.data_simulado, {"simulados": 0, "solved": 0, "possiveis": 0})
            dia["simulados"] += 1
            dia["solved"] += total_solved
            dia["possiveis"] += possiveis

        linhas.append(f"""
        <tr>
            <td>
                <a href="/jamreport/dashboard/simulado/{s.id}">{s.nome}</a>
                {badge_fonte_data(s.descricao)}
            </td>
            <td>{s.data_simulado.strftime('%d/%m/%Y') if s.data_simulado else '-'}</td>
            <td><span class="badge badge-versao">{s.versao}</span></td>
            <td>{s.quantidade_jams}</td>
            <td>{n_equipes}</td>
            <td>{f'{media_score:.1f}' if media_score is not None else '-'}</td>
            <td>{total_solved} / {possiveis if possiveis else '-'}</td>
            <td style="min-width:120px;">
                {barra_taxa(taxa)}
                <div class="taxa-label">{taxa:.0f}%</div>
            </td>
        </tr>
        """)

    tabela = "".join(linhas) if linhas else '<tr><td colspan="8" class="text-center text-muted py-4">Nenhum simulado encontrado com esses filtros.</td></tr>'
    taxa_geral = (total_solved_geral / total_possiveis_geral * 100) if total_possiveis_geral else 0

    heatmap_html = _montar_heatmap(contagem_por_dia)

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>{BASE_HEAD}<title>JAM Report - Dashboard</title></head>
    <body>
        {NAVBAR}
        <div class="container">
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card p-3 mb-0">
                        <div class="stat-label">Simulados (filtro atual)</div>
                        <div class="stat-value">{len(simulados)}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card p-3 mb-0">
                        <div class="stat-label">Participações de equipe</div>
                        <div class="stat-value">{total_equipes_geral}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card p-3 mb-0">
                        <div class="stat-label">JAMs (somado)</div>
                        <div class="stat-value">{total_jams_geral}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card p-3 mb-0" title="Soma de (JAMs x equipes participantes) de cada simulado listado = total de 'oportunidades' de resolver um JAM. A taxa é quantas dessas oportunidades viraram resolução.">
                        <div class="stat-label">Taxa de aproveitamento geral &#9432;</div>
                        <div class="stat-value">{taxa_geral:.0f}%</div>
                        <div class="taxa-label">{total_solved_geral} resolvidos de {total_possiveis_geral or 0} oportunidades (JAMs × equipes)</div>
                    </div>
                </div>
            </div>

            <div class="card p-3">
                <form method="GET" class="row g-2 align-items-end">
                    <div class="col-md-3">
                        <label class="form-label small">Nome contém</label>
                        <input type="text" name="nome" class="form-control form-control-sm" value="{nome_filtro}" placeholder="ex: 2026 ou JAM-11">
                    </div>
                    <div class="col-md-2">
                        <label class="form-label small">Data inicial</label>
                        <input type="date" name="data_inicio" class="form-control form-control-sm" value="{data_inicio}">
                    </div>
                    <div class="col-md-2">
                        <label class="form-label small">Data final</label>
                        <input type="date" name="data_fim" class="form-control form-control-sm" value="{data_fim}">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label small">Equipe/Competidor</label>
                        <select name="equipe_id" class="form-select form-select-sm">
                            <option value="">Todas</option>
                            {"".join(f'<option value="{eq.id}" {"selected" if eq.id == equipe_id else ""}>{eq.name}</option>' for eq in todas_equipes)}
                        </select>
                    </div>
                    <div class="col-md-2">
                        <button type="submit" class="btn btn-sm btn-primary w-100">Filtrar</button>
                    </div>
                </form>
            </div>

            <div class="card p-3">
                <h5 class="mb-1">Mapa de calor — simulados por data</h5>
                <div class="taxa-label mb-3">Cor mais escura = mais simulados naquele dia (dentro do filtro atual). Passe o mouse para ver detalhes.</div>
                {heatmap_html}
            </div>

            <div class="card p-3">
                <h5 class="mb-3">Simulados</h5>
                <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead>
                        <tr>
                            <th>Nome</th><th>Data</th><th>Versão</th><th>JAMs</th>
                            <th>Equipes</th><th>Score médio</th><th>Resolvidos</th><th>Taxa de aproveitamento</th>
                        </tr>
                    </thead>
                    <tbody>{tabela}</tbody>
                </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def _montar_heatmap(contagem_por_dia: dict) -> str:
    if not contagem_por_dia:
        return '<div class="text-muted py-3">Sem datas para exibir com o filtro atual.</div>'

    datas = sorted(contagem_por_dia.keys())
    inicio = datas[0]
    fim = datas[-1]

    # começa na segunda-feira da semana do 'inicio', pra alinhar as colunas certinho
    inicio_grid = inicio - timedelta(days=inicio.weekday())
    fim_grid = fim + timedelta(days=(6 - fim.weekday()))

    max_simulados = max(d["simulados"] for d in contagem_por_dia.values())

    def cor_para(qtd):
        if qtd == 0:
            return "#ebedf0"
        intensidade = qtd / max_simulados if max_simulados else 0
        if intensidade <= 0.25:
            return "#c6e5c9"
        if intensidade <= 0.5:
            return "#7fc98a"
        if intensidade <= 0.75:
            return "#3fa34d"
        return "#1a7431"

    dias_semana_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    semanas = []
    dia_atual = inicio_grid
    semana_atual = []
    while dia_atual <= fim_grid:
        info = contagem_por_dia.get(dia_atual)
        if info:
            taxa_dia = (info["solved"] / info["possiveis"] * 100) if info["possiveis"] else 0
            titulo = (
                f"{dia_atual.strftime('%d/%m/%Y')} — {info['simulados']} simulado(s), "
                f"{info['solved']}/{info['possiveis']} resolvidos ({taxa_dia:.0f}%)"
            )
            cor = cor_para(info["simulados"])
        else:
            titulo = dia_atual.strftime('%d/%m/%Y') + " — sem simulado"
            cor = "#f4f6f8"

        semana_atual.append(
            f'<div class="heat-cell" style="background:{cor};" title="{titulo}"></div>'
        )

        if dia_atual.weekday() == 6:  # domingo fecha a semana
            semanas.append(f'<div class="heat-week">{"".join(semana_atual)}</div>')
            semana_atual = []

        dia_atual += timedelta(days=1)

    if semana_atual:
        semanas.append(f'<div class="heat-week">{"".join(semana_atual)}</div>')

    legenda_dias = "".join(f'<div style="font-size:10px;color:#9ca3af;height:16px;line-height:16px;">{d[0]}</div>' for d in dias_semana_labels)

    return f"""
    <div style="display:flex; gap:6px; overflow-x:auto;">
        <div style="display:flex; flex-direction:column;">{legenda_dias}</div>
        <div class="heat-grid">{''.join(semanas)}</div>
    </div>
    <div class="taxa-label mt-2">
        {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}
    </div>
    """


# ---------------------------------------------------------------------------
# Detalhe de um simulado
# ---------------------------------------------------------------------------

@dashboard_bp.route("/dashboard/simulado/<int:simulado_id>")
def dashboard_simulado(simulado_id):
    simulado = Simulado.query.get(simulado_id)
    if simulado is None:
        abort(404)

    metrics = (
        ChallengeMetric.query
        .filter_by(simulado_id=simulado.id)
        .join(Challenge, ChallengeMetric.challenge_id == Challenge.id)
        .order_by(Challenge.title)
        .all()
    )

    linhas_jam = []
    labels_chart = []
    iniciados_chart = []
    solved_chart = []
    total_iniciaram = total_resolveram = total_tentaram = total_dicas = total_reinicios = 0

    for m in metrics:
        titulo = m.challenge.title or m.challenge.aws_challenge_id
        labels_chart.append(titulo)
        iniciados_chart.append(m.num_teams_started or 0)
        solved_chart.append(m.num_teams_solved or 0)

        total_iniciaram += m.num_teams_started or 0
        total_resolveram += m.num_teams_solved or 0
        total_tentaram += m.num_teams_attempted or 0
        total_dicas += m.num_clues_requested or 0
        total_reinicios += m.number_of_restarts_used or 0

        taxa_jam = ((m.num_teams_solved or 0) / m.num_teams_started * 100) if m.num_teams_started else 0
        _, label_dif, classe_dif = bucket_dificuldade(m.avg_challenge_difficulty)

        linhas_jam.append(f"""
        <tr>
            <td>{titulo}</td>
            <td>{m.num_teams_started or 0}</td>
            <td>{m.num_teams_solved or 0}</td>
            <td>{m.num_teams_attempted or 0}</td>
            <td>{m.num_clues_requested or 0}</td>
            <td>{m.number_of_restarts_used or 0}</td>
            <td><span class="badge {classe_dif}">{label_dif}</span></td>
            <td>{fmt_ms(m.time_to_completed_mean_ms)}</td>
            <td style="min-width:100px;">{barra_taxa(taxa_jam, '#059669')}<div class="taxa-label">{taxa_jam:.0f}%</div></td>
        </tr>
        """)

    equipes = (
        SimuladoTeam.query
        .filter_by(simulado_id=simulado.id)
        .join(Team, SimuladoTeam.team_id == Team.id)
        # MariaDB não suporta a sintaxe NULLS LAST (isso é PostgreSQL/Oracle);
        # o truque abaixo funciona em qualquer banco: ordena primeiro por
        # "é nulo?" (False=0 vem antes de True=1), depois pelo valor em si.
        .order_by(SimuladoTeam.final_rank.is_(None), SimuladoTeam.final_rank.asc())
        .all()
    )

    linhas_equipe = []
    total_solved_geral = total_not_started_geral = total_started_geral = total_attempted_geral = 0

    for st in equipes:
        n_status = (
            db.session.query(TeamChallengeResult.status, func.count(TeamChallengeResult.id))
            .filter_by(simulado_team_id=st.id).group_by(TeamChallengeResult.status).all()
        )
        status_map = {status: qtd for status, qtd in n_status}
        solved, not_started = status_map.get('SOLVED', 0), status_map.get('NOT_STARTED', 0)
        started, attempted = status_map.get('STARTED', 0), status_map.get('ATTEMPTED', 0)

        total_solved_geral += solved
        total_not_started_geral += not_started
        total_started_geral += started
        total_attempted_geral += attempted

        taxa_equipe = (solved / simulado.quantidade_jams * 100) if simulado.quantidade_jams else 0

        cheating_badge = (
            ' <span class="badge badge-cheating" title="Marcado pela AWS como possível uso indevido/fraude">⚠ Suspeita de fraude</span>'
            if st.suspected_of_cheating else ""
        )

        linhas_equipe.append(f"""
        <tr>
            <td>{st.team.name}{cheating_badge}</td>
            <td>{st.final_rank if st.final_rank is not None else '-'}</td>
            <td>{f'{st.final_score:.1f}' if st.final_score is not None else '-'}</td>
            <td>{not_started}</td><td>{started}</td><td>{attempted}</td><td>{solved}</td>
            <td>{st.number_of_restarts_used or 0}</td>
            <td>{fmt_segundos(st.time_first_started_to_last_completion_seconds)}</td>
            <td style="min-width:100px;">{barra_taxa(taxa_equipe)}<div class="taxa-label">{taxa_equipe:.0f}% ({solved}/{simulado.quantidade_jams})</div></td>
        </tr>
        """)

    # --- detalhe: cada JAM individualmente, por equipe (o que estava faltando) ---
    detalhe_equipes_html = []
    for st in equipes:
        resultados = (
            TeamChallengeResult.query
            .filter_by(simulado_team_id=st.id)
            .join(Challenge, TeamChallengeResult.challenge_id == Challenge.id)
            .order_by(Challenge.title)
            .all()
        )
        # não iniciados primeiro, pra ficar fácil ver o que falta
        ordem_status = {"NOT_STARTED": 0, "STARTED": 1, "ATTEMPTED": 2, "SOLVED": 3}
        resultados.sort(key=lambda r: ordem_status.get(r.status, 9))

        linhas_detalhe = []
        for r in resultados:
            titulo = r.challenge.title or r.challenge.aws_challenge_id
            feedback_title = r.feedback_comments.replace('"', "'") if r.feedback_comments else ""
            titulo_html = f'<span title="{feedback_title}">{titulo} {"💬" if r.feedback_comments else ""}</span>'
            linhas_detalhe.append(f"""
            <tr>
                <td>{titulo_html}</td>
                <td>{badge_status(r.status)}</td>
                <td>{r.num_completed_tasks if r.num_completed_tasks is not None else '-'}</td>
                <td>{r.num_incorrect_answers if r.num_incorrect_answers is not None else '-'}</td>
                <td>{r.num_clues_used if r.num_clues_used is not None else '-'}</td>
                <td>{r.total_number_of_attempts if r.total_number_of_attempts is not None else '-'}</td>
                <td>{fmt_ms(r.time_to_completed_challenge_ms)}</td>
            </tr>
            """)

        tabela_detalhe = "".join(linhas_detalhe) if linhas_detalhe else '<tr><td colspan="7" class="text-center text-muted py-3">Sem JAMs registrados para esta equipe.</td></tr>'

        detalhe_equipes_html.append(f"""
        <div class="card p-3">
            <h5 class="mb-1">Detalhe por JAM — equipe {st.team.name}</h5>
            <div class="taxa-label mb-1">💬 = tem comentário de feedback registrado (passe o mouse para ler). Ordenado com "não iniciado" primeiro.</div>
            <div class="taxa-label mb-3">
                ⓘ "Resolvido" vem diretamente da própria AWS (quem consta como solucionador do JAM), não é calculado por nós.
                A AWS não informa a quantidade total de tarefas de cada JAM — só as concluídas — e cada JAM tem uma
                quantidade diferente e não padronizada. Por isso "Tarefas concluídas" varia bastante entre JAMs
                mesmo quando todos estão Resolvidos: não dá pra comparar esse número entre JAMs diferentes.
            </div>
            <div class="table-responsive">
            <table class="table table-hover align-middle">
                <thead><tr>
                    <th>JAM</th><th>Status</th><th>Tarefas concluídas</th>
                    <th>Respostas incorretas</th><th>Dicas usadas</th><th>Tentativas</th><th>Tempo até resolver</th>
                </tr></thead>
                <tbody>{tabela_detalhe}</tbody>
            </table>
            </div>
        </div>
        """)

    detalhe_equipes_html = "".join(detalhe_equipes_html)

    # --- uso de ferramentas (CLI/Console/CodeWhisperer), agregado a nível de rede pelo simulado ---
    total_cli = sum(m.num_participants_used_aws_cli or 0 for m in metrics)
    total_console = sum(m.num_participants_used_aws_console or 0 for m in metrics)
    total_codewhisperer = sum(m.num_participants_used_codewhisperer or 0 for m in metrics)
    total_support_chats = sum(m.support_chat_requests or 0 for m in metrics)

    ferramentas_html = ""
    if total_cli or total_console or total_codewhisperer or total_support_chats:
        ferramentas_html = f"""
        <div class="card p-3">
            <h5 class="mb-3">Uso de ferramentas (somado em todos os JAMs deste simulado)</h5>
            <div class="row g-2">
                <div class="col-6 col-md-3"><div class="card p-2 text-center mb-0">
                    <div class="stat-label">Usaram AWS CLI</div><div class="stat-value" style="font-size:22px;">{total_cli}</div>
                </div></div>
                <div class="col-6 col-md-3"><div class="card p-2 text-center mb-0">
                    <div class="stat-label">Usaram Console</div><div class="stat-value" style="font-size:22px;">{total_console}</div>
                </div></div>
                <div class="col-6 col-md-3"><div class="card p-2 text-center mb-0">
                    <div class="stat-label">Usaram CodeWhisperer</div><div class="stat-value" style="font-size:22px;">{total_codewhisperer}</div>
                </div></div>
                <div class="col-6 col-md-3"><div class="card p-2 text-center mb-0">
                    <div class="stat-label">Chats de suporte pedidos</div><div class="stat-value" style="font-size:22px;">{total_support_chats}</div>
                </div></div>
            </div>
        </div>
        """


    tabela_jam = "".join(linhas_jam) if linhas_jam else '<tr><td colspan="9" class="text-center text-muted py-3">Sem dados de JAMs.</td></tr>'
    tabela_equipe = "".join(linhas_equipe) if linhas_equipe else '<tr><td colspan="10" class="text-center text-muted py-3">Sem equipes.</td></tr>'

    total_tentativas_geral = total_not_started_geral + total_started_geral + total_attempted_geral + total_solved_geral
    taxa_geral_simulado = (total_solved_geral / total_tentativas_geral * 100) if total_tentativas_geral else 0

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>{BASE_HEAD}<title>JAM Report - {simulado.nome}</title></head>
    <body>
        {NAVBAR}
        <div class="container">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h4 class="mb-0">{simulado.nome} <span class="badge badge-versao">v{simulado.versao}</span> {badge_fonte_data(simulado.descricao)}</h4>
                <a href="/jamreport/dashboard" class="btn btn-sm btn-outline-secondary">&larr; Voltar</a>
            </div>
            <p class="text-muted mb-4">
                Data: {simulado.data_simulado.strftime('%d/%m/%Y') if simulado.data_simulado else '-'}
                &nbsp;|&nbsp; {simulado.quantidade_jams} JAMs &nbsp;|&nbsp; {len(equipes)} equipe(s)
                &nbsp;|&nbsp; Taxa geral: <strong>{taxa_geral_simulado:.0f}%</strong>
                ({total_solved_geral} resolvidos de {total_tentativas_geral} JAM×equipe)
            </p>

            <div class="card p-3">
                <h5 class="mb-3">Equipes solucionando por JAM (iniciado vs. resolvido)</h5>
                <canvas id="chartJams" height="90"></canvas>
            </div>

            <div class="card p-3">
                <h5 class="mb-3">Desempenho por JAM</h5>
                <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead><tr>
                        <th>JAM</th><th>Iniciaram</th><th>Resolveram</th><th>Tentaram</th>
                        <th>Dicas</th><th>Reinícios</th><th>Dificuldade</th><th>Tempo médio</th><th>Taxa de resolução</th>
                    </tr></thead>
                    <tbody>{tabela_jam}</tbody>
                    <tfoot>
                        <tr class="fw-bold" style="border-top: 2px solid #d1d5db;">
                            <td>Total</td>
                            <td>{total_iniciaram}</td>
                            <td>{total_resolveram}</td>
                            <td>{total_tentaram}</td>
                            <td>{total_dicas}</td>
                            <td>{total_reinicios}</td>
                            <td colspan="3"></td>
                        </tr>
                    </tfoot>
                </table>
                </div>
            </div>

            <div class="card p-3">
                <h5 class="mb-3">Desempenho por equipe</h5>
                <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead><tr>
                        <th>Equipe</th><th>Rank</th><th>Score</th><th>Não iniciados</th><th>Iniciados</th>
                        <th>Tentados</th><th>Resolvidos</th><th>Reinícios</th><th>Tempo total</th><th>Taxa de aproveitamento</th>
                    </tr></thead>
                    <tbody>{tabela_equipe}</tbody>
                </table>
                </div>
            </div>

            {ferramentas_html}

            {detalhe_equipes_html}
        </div>
        <script>
            new Chart(document.getElementById('chartJams'), {{
                type: 'bar',
                data: {{
                    labels: {json.dumps(labels_chart)},
                    datasets: [
                        {{ label: 'Iniciaram', data: {json.dumps(iniciados_chart)}, backgroundColor: '#93c5fd' }},
                        {{ label: 'Resolveram', data: {json.dumps(solved_chart)}, backgroundColor: '#2563eb' }}
                    ]
                }},
                options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
            }});
        </script>
    </body>
    </html>
    """
    return html


# ---------------------------------------------------------------------------
# Catálogo de JAMs (todos os simulados combinados)
# ---------------------------------------------------------------------------

@dashboard_bp.route("/dashboard/jams")
def dashboard_jams():
    data_inicio = (request.args.get("data_inicio") or "").strip()
    data_fim = (request.args.get("data_fim") or "").strip()

    simulados_query = Simulado.query
    if data_inicio:
        simulados_query = simulados_query.filter(Simulado.data_simulado >= data_inicio)
    if data_fim:
        simulados_query = simulados_query.filter(Simulado.data_simulado <= data_fim)
    simulado_ids = [s.id for s in simulados_query.all()]

    challenges = Challenge.query.order_by(Challenge.title).all()

    linhas = []
    for c in challenges:
        if simulado_ids:
            vezes = SimuladoChallenge.query.filter(
                SimuladoChallenge.challenge_id == c.id,
                SimuladoChallenge.simulado_id.in_(simulado_ids),
            ).count()
            metrics = ChallengeMetric.query.filter(
                ChallengeMetric.challenge_id == c.id,
                ChallengeMetric.simulado_id.in_(simulado_ids),
            ).all()
        else:
            vezes = 0
            metrics = []

        if vezes == 0:
            continue  # não apareceu no período filtrado

        soma_started = sum(m.num_teams_started or 0 for m in metrics)
        soma_solved = sum(m.num_teams_solved or 0 for m in metrics)
        taxa = (soma_solved / soma_started * 100) if soma_started else 0

        dificuldades = [m.avg_challenge_difficulty for m in metrics if m.avg_challenge_difficulty]
        dif_media = sum(dificuldades) / len(dificuldades) if dificuldades else None
        _, label_dif, classe_dif = bucket_dificuldade(dif_media)

        linhas.append((vezes, f"""
        <tr>
            <td>{c.title or c.aws_challenge_id}</td>
            <td class="text-muted small">{c.aws_challenge_id}</td>
            <td>{vezes}</td>
            <td>{soma_started}</td>
            <td>{soma_solved}</td>
            <td style="min-width:100px;">{barra_taxa(taxa, '#059669')}<div class="taxa-label">{taxa:.0f}%</div></td>
            <td><span class="badge {classe_dif}">{label_dif}</span></td>
        </tr>
        """))

    linhas.sort(key=lambda x: x[0], reverse=True)
    total_jams_encontrados = len(linhas)

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    if per_page not in (10, 20, 50, 100):
        per_page = 20
    pagina_linhas, total_paginas, page = paginar(linhas, page, per_page)

    tabela = "".join(l for _, l in pagina_linhas) if pagina_linhas else '<tr><td colspan="7" class="text-center text-muted py-4">Nenhum JAM encontrado no período.</td></tr>'
    paginacao_html = controles_paginacao(page, total_paginas, per_page, {"data_inicio": data_inicio, "data_fim": data_fim})

    # distribuição de dificuldade (sobre os JAMs distintos exibidos)
    contagem_dif = {"Fácil": 0, "Médio": 0, "Difícil": 0, "Sem avaliação": 0}
    for c in challenges:
        if simulado_ids:
            metrics = ChallengeMetric.query.filter(
                ChallengeMetric.challenge_id == c.id,
                ChallengeMetric.simulado_id.in_(simulado_ids),
            ).all()
        else:
            metrics = []
        dificuldades = [m.avg_challenge_difficulty for m in metrics if m.avg_challenge_difficulty]
        if not dificuldades:
            continue
        media = sum(dificuldades) / len(dificuldades)
        _, label, _ = bucket_dificuldade(media)
        contagem_dif[label] = contagem_dif.get(label, 0) + 1

    total_dif = sum(contagem_dif.values()) or 1
    linhas_dif = "".join(
        f'<div class="col-6 col-md-3"><div class="card p-2 text-center mb-0">'
        f'<div class="stat-label">{k}</div>'
        f'<div class="stat-value" style="font-size:20px;">{v} ({v/total_dif*100:.0f}%)</div>'
        f'</div></div>'
        for k, v in contagem_dif.items()
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>{BASE_HEAD}<title>JAM Report - Catálogo de JAMs</title></head>
    <body>
        {NAVBAR}
        <div class="container">
            <h4 class="mb-3">Catálogo de JAMs (challenges)</h4>

            <div class="card p-3">
                <form method="GET" class="row g-2 align-items-end">
                    <div class="col-md-4">
                        <label class="form-label small">Data inicial</label>
                        <input type="date" name="data_inicio" class="form-control form-control-sm" value="{data_inicio}">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small">Data final</label>
                        <input type="date" name="data_fim" class="form-control form-control-sm" value="{data_fim}">
                    </div>
                    <div class="col-md-2">
                        <button type="submit" class="btn btn-sm btn-primary w-100">Filtrar</button>
                    </div>
                </form>
            </div>

            <div class="card p-3">
                <h6 class="mb-2">Distribuição de dificuldade (aproximada, derivada da avaliação das equipes)</h6>
                <div class="row g-2">{linhas_dif}</div>
            </div>

            <div class="card p-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0">{total_jams_encontrados} JAM(s) encontrado(s)</h6>
                </div>
                <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead><tr>
                        <th>JAM</th><th>ID técnico</th><th>Vezes executado</th>
                        <th>Total tentativas (equipes)</th><th>Total resolvidos</th>
                        <th>Taxa de resolução</th><th>Dificuldade</th>
                    </tr></thead>
                    <tbody>{tabela}</tbody>
                </table>
                </div>
                {paginacao_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html


# ---------------------------------------------------------------------------
# Ranking de serviços AWS
# ---------------------------------------------------------------------------

@dashboard_bp.route("/dashboard/servicos")
def dashboard_servicos():
    data_inicio = (request.args.get("data_inicio") or "").strip()
    data_fim = (request.args.get("data_fim") or "").strip()

    simulados_query = Simulado.query
    if data_inicio:
        simulados_query = simulados_query.filter(Simulado.data_simulado >= data_inicio)
    if data_fim:
        simulados_query = simulados_query.filter(Simulado.data_simulado <= data_fim)
    simulado_ids = [s.id for s in simulados_query.all()]

    servicos = AwsService.query.order_by(AwsService.service_name).all()

    linhas = []
    for serv in servicos:
        if not simulado_ids:
            continue

        aparicoes = (
            ChallengeService.query
            .join(ChallengeMetric, ChallengeService.challenge_metric_id == ChallengeMetric.id)
            .filter(
                ChallengeService.aws_service_id == serv.id,
                ChallengeMetric.simulado_id.in_(simulado_ids),
            )
            .count()
        )
        simulados_distintos = (
            db.session.query(func.count(func.distinct(ChallengeMetric.simulado_id)))
            .join(ChallengeService, ChallengeService.challenge_metric_id == ChallengeMetric.id)
            .filter(
                ChallengeService.aws_service_id == serv.id,
                ChallengeMetric.simulado_id.in_(simulado_ids),
            )
            .scalar() or 0
        )

        if aparicoes == 0:
            continue

        linhas.append((aparicoes, f"""
        <tr>
            <td>{serv.service_name}</td>
            <td>{aparicoes}</td>
            <td>{simulados_distintos}</td>
        </tr>
        """))

    linhas.sort(key=lambda x: x[0], reverse=True)
    total_servicos_encontrados = len(linhas)

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    if per_page not in (10, 20, 50, 100):
        per_page = 20
    pagina_linhas, total_paginas, page = paginar(linhas, page, per_page)

    tabela = "".join(l for _, l in pagina_linhas) if pagina_linhas else '<tr><td colspan="3" class="text-center text-muted py-4">Nenhum serviço AWS registrado no período.</td></tr>'
    paginacao_html = controles_paginacao(page, total_paginas, per_page, {"data_inicio": data_inicio, "data_fim": data_fim})

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>{BASE_HEAD}<title>JAM Report - Serviços AWS</title></head>
    <body>
        {NAVBAR}
        <div class="container">
            <h4 class="mb-3">Serviços AWS utilizados</h4>
            <p class="text-muted">
                "Aparições" conta cada vez que o serviço aparece associado a um JAM dentro de um
                simulado. "Simulados" conta em quantos treinamentos distintos o serviço apareceu
                pelo menos uma vez — útil pra ver se um serviço específico (ex: S3, IAM) está
                sendo praticado com frequência ao longo do tempo.
            </p>

            <div class="card p-3">
                <form method="GET" class="row g-2 align-items-end">
                    <div class="col-md-4">
                        <label class="form-label small">Data inicial</label>
                        <input type="date" name="data_inicio" class="form-control form-control-sm" value="{data_inicio}">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small">Data final</label>
                        <input type="date" name="data_fim" class="form-control form-control-sm" value="{data_fim}">
                    </div>
                    <div class="col-md-2">
                        <button type="submit" class="btn btn-sm btn-primary w-100">Filtrar</button>
                    </div>
                </form>
            </div>

            <div class="card p-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0">{total_servicos_encontrados} serviço(s) encontrado(s)</h6>
                </div>
                <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead><tr><th>Serviço AWS</th><th>Aparições (JAM × simulado)</th><th>Simulados distintos</th></tr></thead>
                    <tbody>{tabela}</tbody>
                </table>
                </div>
                {paginacao_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html


# ---------------------------------------------------------------------------
# Equipes / competidores — visão consolidada e histórico individual
# ---------------------------------------------------------------------------

@dashboard_bp.route("/dashboard/equipes")
def dashboard_equipes():
    equipes = Team.query.order_by(Team.name).all()

    linhas = []
    for eq in equipes:
        participacoes = SimuladoTeam.query.filter_by(team_id=eq.id).all()
        if not participacoes:
            continue

        n_simulados = len(participacoes)
        soma_score = sum(p.final_score for p in participacoes if p.final_score is not None)
        n_com_score = sum(1 for p in participacoes if p.final_score is not None)
        media_score = (soma_score / n_com_score) if n_com_score else None
        total_resolvidos = sum(p.number_challenges_solved or 0 for p in participacoes)
        total_possiveis = sum(
            (Simulado.query.get(p.simulado_id).quantidade_jams or 0) for p in participacoes
        )
        taxa = (total_resolvidos / total_possiveis * 100) if total_possiveis else 0
        alertas = sum(1 for p in participacoes if p.suspected_of_cheating)

        alerta_html = f' <span class="badge badge-cheating">{alertas} alerta(s)</span>' if alertas else ""

        linhas.append(f"""
        <tr>
            <td><a href="/jamreport/dashboard/equipe/{eq.id}">{eq.name}</a>{alerta_html}</td>
            <td>{n_simulados}</td>
            <td>{f'{media_score:.1f}' if media_score is not None else '-'}</td>
            <td>{total_resolvidos} / {total_possiveis or '-'}</td>
            <td style="min-width:100px;">{barra_taxa(taxa)}<div class="taxa-label">{taxa:.0f}%</div></td>
        </tr>
        """)

    tabela = "".join(linhas) if linhas else '<tr><td colspan="5" class="text-center text-muted py-4">Nenhuma equipe com participação registrada.</td></tr>'

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>{BASE_HEAD}<title>JAM Report - Equipes</title></head>
    <body>
        {NAVBAR}
        <div class="container">
            <h4 class="mb-3">Equipes / Competidores</h4>
            <div class="card p-3">
                <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead><tr>
                        <th>Equipe</th><th>Simulados participados</th><th>Score médio</th>
                        <th>Total resolvidos</th><th>Taxa de aproveitamento geral</th>
                    </tr></thead>
                    <tbody>{tabela}</tbody>
                </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@dashboard_bp.route("/dashboard/equipe/<int:team_id>")
def dashboard_equipe_detalhe(team_id):
    equipe = Team.query.get(team_id)
    if equipe is None:
        abort(404)

    participacoes = (
        SimuladoTeam.query
        .filter_by(team_id=team_id)
        .join(Simulado, SimuladoTeam.simulado_id == Simulado.id)
        .order_by(Simulado.data_simulado.desc())
        .all()
    )

    linhas = []
    total_resolvidos = total_possiveis = 0

    for p in participacoes:
        sim = Simulado.query.get(p.simulado_id)
        n_status = (
            db.session.query(TeamChallengeResult.status, func.count(TeamChallengeResult.id))
            .filter_by(simulado_team_id=p.id).group_by(TeamChallengeResult.status).all()
        )
        status_map = {status: qtd for status, qtd in n_status}
        solved = status_map.get('SOLVED', 0)

        possiveis = sim.quantidade_jams or 0
        taxa = (solved / possiveis * 100) if possiveis else 0
        total_resolvidos += solved
        total_possiveis += possiveis

        alerta_html = ' <span class="badge badge-cheating">⚠ Suspeita de fraude</span>' if p.suspected_of_cheating else ""

        linhas.append(f"""
        <tr>
            <td><a href="/jamreport/dashboard/simulado/{sim.id}">{sim.nome}</a>{alerta_html}</td>
            <td>{sim.data_simulado.strftime('%d/%m/%Y') if sim.data_simulado else '-'}</td>
            <td>{f'{p.final_score:.1f}' if p.final_score is not None else '-'}</td>
            <td>{p.final_rank if p.final_rank is not None else '-'}</td>
            <td>{status_map.get('NOT_STARTED', 0)}</td>
            <td>{status_map.get('STARTED', 0)}</td>
            <td>{status_map.get('ATTEMPTED', 0)}</td>
            <td>{solved}</td>
            <td>{p.number_of_restarts_used or 0}</td>
            <td style="min-width:100px;">{barra_taxa(taxa)}<div class="taxa-label">{taxa:.0f}%</div></td>
        </tr>
        """)

    tabela = "".join(linhas) if linhas else '<tr><td colspan="10" class="text-center text-muted py-4">Sem participações registradas.</td></tr>'
    taxa_geral = (total_resolvidos / total_possiveis * 100) if total_possiveis else 0

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>{BASE_HEAD}<title>JAM Report - {equipe.name}</title></head>
    <body>
        {NAVBAR}
        <div class="container">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h4 class="mb-0">{equipe.name}</h4>
                <a href="/jamreport/dashboard/equipes" class="btn btn-sm btn-outline-secondary">&larr; Voltar</a>
            </div>
            <p class="text-muted mb-4">
                {len(participacoes)} simulado(s) &nbsp;|&nbsp;
                Taxa de aproveitamento geral: <strong>{taxa_geral:.0f}%</strong>
                ({total_resolvidos} de {total_possiveis} JAMs possíveis)
            </p>

            <div class="card p-3">
                <h5 class="mb-3">Histórico em todos os simulados</h5>
                <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead><tr>
                        <th>Simulado</th><th>Data</th><th>Score</th><th>Rank</th>
                        <th>Não iniciados</th><th>Iniciados</th><th>Tentados</th><th>Resolvidos</th>
                        <th>Reinícios</th><th>Taxa</th>
                    </tr></thead>
                    <tbody>{tabela}</tbody>
                </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html
