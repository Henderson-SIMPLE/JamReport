"""
Importador de relatórios JSON do AWS Skill Builder (JAMs/Simulados).

Uso típico (dentro de uma rota Flask):

    from services.json_importer import importar_relatorio, ImportError_

    try:
        resultado = importar_relatorio(
            raw_bytes=arquivo.read(),
            original_filename=arquivo.filename,
            nome_simulado="Simulado_JAM-19062026",
            user_id=current_user.id,
        )
    except ImportError_ as e:
        # mostrar e.args[0] para o usuário
        ...
"""

import hashlib
import json
import re
from datetime import datetime, date

from database import db
from models import (
    ImportedFile,
    Simulado,
    Challenge,
    SimuladoChallenge,
    Team,
    Participant,
    TeamMember,
    SimuladoTeam,
    TeamChallengeResult,
    ChallengeSolver,
    ChallengeMetric,
    AwsService,
    ChallengeService,
    TeamService,
    EventFeedback,
)


class ImportError_(Exception):
    """Erro de importação com mensagem amigável para exibir ao usuário."""
    pass


NOME_SIMULADO_REGEX = re.compile(
    r"^Simulado_JAM-(\d{2})(\d{2})(\d{4})([a-zA-Z]?)$"
)

# Procura 8 dígitos (DDMMAAAA) logo antes da extensão .json no nome do arquivo,
# ex: "Simulado_JAM-13082026.json", "relatorio_13082026.json", "13082026.json"
DATA_NO_FILENAME_REGEX = re.compile(r"(\d{2})(\d{2})(\d{4})\.json$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _carregar_json(raw_bytes: bytes) -> dict:
    """
    Alguns exports do AWS Skill Builder vêm com o JSON 'escapado' dentro de
    uma string (double-encoded). Este helper lida com os dois casos.
    """
    try:
        texto = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ImportError_(f"Arquivo não está em UTF-8 válido: {e}")

    try:
        dado = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ImportError_(f"JSON inválido: {e}")

    if isinstance(dado, str):
        try:
            dado = json.loads(dado)
        except json.JSONDecodeError as e:
            raise ImportError_(f"JSON (duplamente codificado) inválido: {e}")

    if not isinstance(dado, dict):
        raise ImportError_("Formato inesperado: raiz do JSON não é um objeto.")

    return dado


def _parse_nome_simulado(nome: str):
    """
    Extrai (nome_base, data_simulado, versao) de 'Simulado_JAM-DDMMAAAAb'.
    Levanta ImportError_ se o nome não seguir o padrão.
    """
    match = NOME_SIMULADO_REGEX.match(nome.strip())
    if not match:
        raise ImportError_(
            "Nome do simulado fora do padrão esperado "
            "'Simulado_JAM-DDMMAAAA' (ex: Simulado_JAM-19062026 ou "
            "Simulado_JAM-19062026b)."
        )
    dd, mm, aaaa, sufixo = match.groups()
    try:
        data_simulado = date(int(aaaa), int(mm), int(dd))
    except ValueError:
        raise ImportError_(f"Data inválida no nome do simulado: {dd}/{mm}/{aaaa}")

    versao = sufixo.upper() if sufixo else "A"
    nome_base = f"Simulado_JAM-{dd}{mm}{aaaa}"
    return nome_base, data_simulado, versao


def _epoch_ms_to_datetime(valor):
    if valor is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(valor) / 1000.0)
    except (ValueError, TypeError, OverflowError):
        return None


def sugerir_data_relatorio(dado: dict):
    """
    Sugestão de data do simulado a partir do próprio JSON, usando
    lastGeneratedDate (preferência) ou lastUpdatedDate como fallback.

    IMPORTANTE: essa é a data em que a AWS *gerou o relatório*, não
    necessariamente a data em que o simulado foi executado. Costuma
    ficar próxima da data real, mas deve ser tratada como sugestão,
    não como verdade absoluta.
    """
    epoch = dado.get("lastGeneratedDate") or dado.get("lastUpdatedDate")
    dt = _epoch_ms_to_datetime(epoch)
    return dt.date() if dt else None


def extrair_data_do_nome_arquivo(filename: str):
    """
    Tenta extrair uma data DDMMAAAA dos 8 dígitos que antecedem '.json'
    no nome do arquivo (ex: 'Simulado_JAM-13082026.json' -> 13/08/2026).
    Retorna None se o nome não seguir esse padrão ou a data for inválida.
    """
    if not filename:
        return None
    match = DATA_NO_FILENAME_REGEX.search(filename)
    if not match:
        return None
    dd, mm, aaaa = match.groups()
    try:
        return date(int(aaaa), int(mm), int(dd))
    except ValueError:
        return None


def _proximo_nome_disponivel(data_simulado: date) -> str:
    """
    Gera 'Simulado_JAM-DDMMAAAA' para a data dada; se já existir, tenta
    sufixos b, c, d... até achar um nome livre.
    """
    base = f"Simulado_JAM-{data_simulado.day:02d}{data_simulado.month:02d}{data_simulado.year:04d}"

    if Simulado.query.filter_by(nome=base).first() is None:
        return base

    for letra in "bcdefghijklmnopqrstuvwxyz":
        candidato = f"{base}{letra}"
        if Simulado.query.filter_by(nome=candidato).first() is None:
            return candidato

    raise ImportError_(
        f"Não foi possível gerar um nome automático livre para {base} "
        f"(todas as variações de a-z já estão em uso)."
    )


def _get_or_create_challenge(cache: dict, aws_challenge_id: str, titulo: str = None) -> Challenge:
    if aws_challenge_id in cache:
        challenge = cache[aws_challenge_id]
        if titulo and not challenge.title:
            challenge.title = titulo
        return challenge

    challenge = Challenge.query.filter_by(aws_challenge_id=aws_challenge_id).first()
    if challenge is None:
        challenge = Challenge(aws_challenge_id=aws_challenge_id, title=titulo)
        db.session.add(challenge)
        db.session.flush()  # garante challenge.id disponível
    elif titulo and not challenge.title:
        challenge.title = titulo

    cache[aws_challenge_id] = challenge
    return challenge


def _get_or_create_team(cache: dict, nome_time: str) -> Team:
    if nome_time in cache:
        return cache[nome_time]
    team = Team.query.filter_by(name=nome_time).first()
    if team is None:
        team = Team(name=nome_time, aws_team_name=nome_time)
        db.session.add(team)
        db.session.flush()
    cache[nome_time] = team
    return team


def _get_or_create_participant(cache: dict, aws_identifier: str, nome_fallback: str = None) -> Participant:
    if aws_identifier in cache:
        return cache[aws_identifier]
    participant = Participant.query.filter_by(aws_identifier=aws_identifier).first()
    if participant is None:
        participant = Participant(
            name=nome_fallback or aws_identifier,
            aws_identifier=aws_identifier,
        )
        db.session.add(participant)
        db.session.flush()
    cache[aws_identifier] = participant
    return participant


def _get_or_create_aws_service(cache: dict, service_name: str) -> AwsService:
    if service_name in cache:
        return cache[service_name]
    service = AwsService.query.filter_by(service_name=service_name).first()
    if service is None:
        service = AwsService(service_name=service_name)
        db.session.add(service)
        db.session.flush()
    cache[service_name] = service
    return service


def _status_da_tentativa(started_item: dict) -> str:
    if started_item.get("teamMembersSolved"):
        return "SOLVED"
    if (started_item.get("totalNumberOfAttempts") or 0) > 0:
        return "ATTEMPTED"
    return "STARTED"


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def importar_relatorio(raw_bytes: bytes, original_filename: str, user_id: int,
                        nome_simulado: str = None) -> dict:
    """
    Importa um relatório JSON de simulado AWS JAM.

    nome_simulado:
        - Se informado, precisa seguir o padrão 'Simulado_JAM-DDMMAAAA[letra]'.
        - Se None/vazio, o nome é gerado automaticamente a partir da data de
          geração do relatório (ver sugerir_data_relatorio), com sufixo de
          versão automático (b, c, ...) se já existir um simulado nessa data.

    Retorna um dict com um resumo do que foi importado.
    Levanta ImportError_ em qualquer falha de validação (nada é gravado no banco).
    """

    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    existente = ImportedFile.query.filter_by(sha256=sha256).first()
    if existente is not None:
        raise ImportError_(
            f"Este arquivo já foi importado anteriormente em "
            f"{existente.imported_at:%d/%m/%Y %H:%M} "
            f"(arquivo original: {existente.original_filename})."
        )

    dado = _carregar_json(raw_bytes)

    fonte_data = None  # para registrar em Simulado.descricao

    if nome_simulado and nome_simulado.strip():
        nome_base, data_simulado, versao = _parse_nome_simulado(nome_simulado)
        nome_final = nome_simulado.strip()
        fonte_data = "nome informado manualmente"
        if Simulado.query.filter_by(nome=nome_final).first() is not None:
            raise ImportError_(f"Já existe um simulado cadastrado com o nome '{nome_final}'.")
    else:
        data_do_arquivo = extrair_data_do_nome_arquivo(original_filename)
        if data_do_arquivo is not None:
            data_sugerida = data_do_arquivo
            fonte_data = "extraída do nome do arquivo (confiável)"
        else:
            data_sugerida = sugerir_data_relatorio(dado)
            fonte_data = (
                "estimada via data de geração do relatório na AWS "
                "(pode divergir da data real do simulado — confira)"
            )

        if data_sugerida is None:
            raise ImportError_(
                "Não foi possível determinar a data do simulado: o nome do "
                "arquivo não termina em DDMMAAAA.json e o JSON não traz "
                "lastGeneratedDate/lastUpdatedDate. Informe o nome do "
                "simulado manualmente."
            )
        nome_final = _proximo_nome_disponivel(data_sugerida)
        nome_base, data_simulado, versao = _parse_nome_simulado(nome_final)

    team_metrics = dado.get("teamMetrics", [])
    challenge_metrics_json = dado.get("challengeMetrics", [])
    challenge_titles = dado.get("challengeTitles", {}) or {}
    event_feedback_json = dado.get("eventFeedback", []) or []
    last_updated = _epoch_ms_to_datetime(dado.get("lastUpdatedDate"))
    last_generated = _epoch_ms_to_datetime(dado.get("lastGeneratedDate"))
    event_name = dado.get("eventName")

    try:
        # --- imported_files -------------------------------------------------
        imported_file = ImportedFile(
            original_filename=original_filename,
            file_size_bytes=len(raw_bytes),
            sha256=sha256,
            mime_type="application/json",
            raw_json=raw_bytes.decode("utf-8"),
            imported_by_user_id=user_id,
        )
        db.session.add(imported_file)
        db.session.flush()

        # --- simulados --------------------------------------------------------
        simulado = Simulado(
            nome=nome_final,
            nome_base=nome_base,
            data_simulado=data_simulado,
            versao=versao,
            descricao=f"Data do simulado: {fonte_data}." if fonte_data else None,
            quantidade_jams=len(challenge_titles) or len(challenge_metrics_json),
            event_name=event_name,
            last_updated_aws=last_updated,
            last_generated_aws=last_generated,
            imported_file_id=imported_file.id,
        )
        db.session.add(simulado)
        db.session.flush()

        # --- challenges (JAMs) --------------------------------------------
        challenge_cache = {}

        # primeiro os títulos conhecidos, depois qualquer id que só apareça nas métricas
        for aws_id, titulo in challenge_titles.items():
            _get_or_create_challenge(challenge_cache, aws_id, titulo)

        for ordem, cm in enumerate(challenge_metrics_json, start=1):
            aws_id = cm["challengeId"]
            challenge = _get_or_create_challenge(challenge_cache, aws_id)

            if not SimuladoChallenge.query.filter_by(
                simulado_id=simulado.id, challenge_id=challenge.id
            ).first():
                db.session.add(SimuladoChallenge(
                    simulado_id=simulado.id,
                    challenge_id=challenge.id,
                    ordem=ordem,
                ))

            services_cache = {}
            tta = cm.get("timeToFirstAttempt") or {}
            ttc = cm.get("timeToCompletedChallenge") or {}
            gst = cm.get("globalSolveTime") or {}

            metric = ChallengeMetric(
                simulado_id=simulado.id,
                challenge_id=challenge.id,
                num_teams_started=cm.get("numTeamsStarted"),
                num_teams_solved=cm.get("numTeamsSolved"),
                num_teams_attempted=cm.get("numTeamsAttempted"),
                num_clues_requested=cm.get("numCluesRequested"),
                num_completed_tasks=cm.get("numCompletedTasks"),
                num_incorrect_answers=cm.get("numIncorrectAnswers"),
                avg_challenge_rank=cm.get("avgChallengeRank"),
                avg_challenge_difficulty=cm.get("avgChallengeDifficulty"),
                challenge_feedback_count=cm.get("challengeFeedbackCount"),
                learned_something_new=cm.get("learnedSomethingNew"),
                did_not_learn_something_new=cm.get("didNotLearnSomethingNew"),
                time_to_first_attempt_min_ms=tta.get("min"),
                time_to_first_attempt_max_ms=tta.get("max"),
                time_to_first_attempt_mean_ms=tta.get("mean"),
                time_to_completed_min_ms=ttc.get("min"),
                time_to_completed_max_ms=ttc.get("max"),
                time_to_completed_mean_ms=ttc.get("mean"),
                global_solve_time_min=gst.get("min"),
                global_solve_time_max=gst.get("max"),
                global_solve_time_mean=gst.get("mean"),
                number_of_restarts_used=cm.get("numberOfRestartsUsed"),
                total_number_of_aws_accounts_used=cm.get("totalNumberOfAWSAccountsUsed"),
                support_chat_requests=cm.get("supportChatRequests"),
                num_participants_used_aws_cli=cm.get("numParticipantsUsedAwsCli"),
                num_participants_used_aws_console=cm.get("numParticipantsUsedAwsConsole"),
                num_participants_used_codewhisperer=cm.get("numParticipantsUsedCodeWhisperer"),
            )
            db.session.add(metric)
            db.session.flush()

            for service_name in cm.get("awsServicesUsed", []) or []:
                service = _get_or_create_aws_service(services_cache, service_name)
                if not ChallengeService.query.filter_by(
                    challenge_metric_id=metric.id, aws_service_id=service.id
                ).first():
                    db.session.add(ChallengeService(
                        challenge_metric_id=metric.id,
                        aws_service_id=service.id,
                    ))

        # --- teams / participants / resultados -----------------------------
        team_cache = {}
        participant_cache = {}
        aws_service_cache = {}

        for tm in team_metrics:
            nome_time = tm["teamName"]
            team = _get_or_create_team(team_cache, nome_time)

            simulado_team = SimuladoTeam(
                simulado_id=simulado.id,
                team_id=team.id,
                final_score=tm.get("finalScore"),
                final_rank=tm.get("finalRank"),
                number_challenges_solved=tm.get("numberChallengesSolved"),
                time_first_started_to_last_completion_seconds=tm.get(
                    "timeFromFirstStartedChallengeToLastCompletionTime"
                ),
                number_of_restarts_used=tm.get("numberOfRestartsUsed"),
                number_of_aws_accounts_used=tm.get("numberOfAWSAccountsUsed"),
                number_of_support_chats_requested=tm.get("numberOfSupportChatsRequested"),
                suspected_of_cheating=tm.get("suspectedOfCheating"),
            )
            db.session.add(simulado_team)
            db.session.flush()

            # membros da equipe (participants) — só temos nomes aqui, sem aws_identifier
            for nome_membro in tm.get("teamMembers", []) or []:
                participant = _get_or_create_participant(
                    participant_cache,
                    aws_identifier=f"nome::{nome_membro}",  # sem id AWS real disponível neste nível
                    nome_fallback=nome_membro,
                )
                if not TeamMember.query.filter_by(
                    team_id=team.id, participant_id=participant.id
                ).first():
                    db.session.add(TeamMember(team_id=team.id, participant_id=participant.id))

            # serviços AWS usados pela equipe
            for service_name in tm.get("awsServicesUsed", []) or []:
                service = _get_or_create_aws_service(aws_service_cache, service_name)
                if not TeamService.query.filter_by(
                    simulado_team_id=simulado_team.id, aws_service_id=service.id
                ).first():
                    db.session.add(TeamService(
                        simulado_team_id=simulado_team.id,
                        aws_service_id=service.id,
                    ))

            # challenges iniciados (com ou sem solução)
            for item in tm.get("startedChallenges", []) or []:
                aws_id = item["challengeId"]
                challenge = _get_or_create_challenge(challenge_cache, aws_id)

                result = TeamChallengeResult(
                    simulado_team_id=simulado_team.id,
                    challenge_id=challenge.id,
                    status=_status_da_tentativa(item),
                    num_completed_tasks=item.get("numCompletedTasks"),
                    num_incorrect_answers=item.get("numIncorrectAnswers"),
                    time_to_first_attempt_ms=item.get("timeToFirstAttempt"),
                    time_to_completed_challenge_ms=item.get("timeToCompletedChallenge"),
                    num_clues_used=item.get("numCluesUsed"),
                    team_challenge_rating=item.get("teamChallengeRating"),
                    team_challenge_difficulty_rating=item.get("teamChallengeDifficultyRating"),
                    total_number_of_attempts=item.get("totalNumberOfAttempts"),
                    learned_something_new=bool(item.get("learnedSomethingNew")),
                    did_not_learn_something_new=bool(item.get("didNotLearnSomethingNew")),
                    feedback_comments="; ".join(
                        c for c in (item.get("feedbackComments") or []) if c
                    ) or None,
                )
                db.session.add(result)
                db.session.flush()

                for aws_identifier in item.get("teamMembersSolved", []) or []:
                    solver_participant = _get_or_create_participant(
                        participant_cache, aws_identifier=aws_identifier
                    )
                    db.session.add(ChallengeSolver(
                        team_challenge_result_id=result.id,
                        participant_id=solver_participant.id,
                        aws_solver_identifier=aws_identifier,
                    ))

            # challenges não iniciados
            for aws_id in tm.get("notStartedChallenges", []) or []:
                challenge = _get_or_create_challenge(challenge_cache, aws_id)
                db.session.add(TeamChallengeResult(
                    simulado_team_id=simulado_team.id,
                    challenge_id=challenge.id,
                    status="NOT_STARTED",
                ))

        # --- event feedback -------------------------------------------------
        for fb in event_feedback_json:
            if not fb:
                continue
            db.session.add(EventFeedback(
                simulado_id=simulado.id,
                event_rank=fb.get("eventRank"),
                speaker_rank=fb.get("speakerRank"),
                notes=fb.get("notes"),
            ))

        db.session.commit()

    except ImportError_:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise ImportError_(f"Erro inesperado durante a importação: {e}")

    return {
        "simulado_id": simulado.id,
        "nome": simulado.nome,
        "quantidade_jams": simulado.quantidade_jams,
        "quantidade_equipes": len(team_metrics),
        "fonte_data": fonte_data,
    }
