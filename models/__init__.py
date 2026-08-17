"""
Models SQLAlchemy do JAM Report.
Mapeiam 1:1 as tabelas definidas em schema.sql.
Import esperado em app.py / routes: from models import User, Simulado, Challenge, ...
"""

from datetime import datetime
from database import db


# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("ADMIN", "USER", name="user_role"), nullable=False, default="USER")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    imported_files = db.relationship("ImportedFile", back_populates="imported_by", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.username}>"


# ---------------------------------------------------------------------------
# IMPORTED_FILES
# ---------------------------------------------------------------------------
class ImportedFile(db.Model):
    __tablename__ = "imported_files"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size_bytes = db.Column(db.BigInteger)
    sha256 = db.Column(db.CHAR(64), nullable=False, unique=True)
    mime_type = db.Column(db.String(100))
    raw_json = db.Column(db.Text, nullable=False)
    imported_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)

    imported_by = db.relationship("User", back_populates="imported_files")
    simulados = db.relationship("Simulado", back_populates="imported_file", lazy="dynamic")

    def __repr__(self):
        return f"<ImportedFile {self.original_filename}>"


# ---------------------------------------------------------------------------
# SIMULADOS
# ---------------------------------------------------------------------------
class Simulado(db.Model):
    __tablename__ = "simulados"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(150), nullable=False, unique=True)
    nome_base = db.Column(db.String(100))
    data_simulado = db.Column(db.Date, nullable=False)
    versao = db.Column(db.CHAR(1), nullable=False, default="A")
    descricao = db.Column(db.Text)
    criado_em_aws = db.Column(db.DateTime)
    inicio_programado = db.Column(db.DateTime)
    fim_programado = db.Column(db.DateTime)
    duracao_programada_segundos = db.Column(db.Integer)
    quantidade_jams = db.Column(db.SmallInteger, nullable=False, default=0)
    event_name = db.Column(db.String(100))  # eventName (UUID) vindo do JSON da AWS
    last_updated_aws = db.Column(db.DateTime)
    last_generated_aws = db.Column(db.DateTime)
    imported_file_id = db.Column(db.BigInteger, db.ForeignKey("imported_files.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    imported_file = db.relationship("ImportedFile", back_populates="simulados")
    simulado_challenges = db.relationship("SimuladoChallenge", back_populates="simulado", cascade="all, delete-orphan")
    simulado_teams = db.relationship("SimuladoTeam", back_populates="simulado", cascade="all, delete-orphan")
    challenge_metrics = db.relationship("ChallengeMetric", back_populates="simulado", cascade="all, delete-orphan")
    event_feedback = db.relationship("EventFeedback", back_populates="simulado", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Simulado {self.nome}>"


# ---------------------------------------------------------------------------
# CHALLENGES  (= "JAMs" na nomenclatura do projeto)
# ---------------------------------------------------------------------------
class Challenge(db.Model):
    __tablename__ = "challenges"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    aws_challenge_id = db.Column(db.String(150), nullable=False, unique=True)  # ex: "access-s3-via-vpc-endpoint"
    title = db.Column(db.String(255))  # vem de challengeTitles no JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    simulado_challenges = db.relationship("SimuladoChallenge", back_populates="challenge")
    team_challenge_results = db.relationship("TeamChallengeResult", back_populates="challenge")
    challenge_metrics = db.relationship("ChallengeMetric", back_populates="challenge")

    def __repr__(self):
        return f"<Challenge {self.aws_challenge_id}>"


class SimuladoChallenge(db.Model):
    __tablename__ = "simulado_challenges"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    simulado_id = db.Column(db.BigInteger, db.ForeignKey("simulados.id"), nullable=False)
    challenge_id = db.Column(db.BigInteger, db.ForeignKey("challenges.id"), nullable=False)
    ordem = db.Column(db.SmallInteger)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    simulado = db.relationship("Simulado", back_populates="simulado_challenges")
    challenge = db.relationship("Challenge", back_populates="simulado_challenges")

    __table_args__ = (
        db.UniqueConstraint("simulado_id", "challenge_id", name="uk_simulado_challenge"),
        db.UniqueConstraint("simulado_id", "ordem", name="uk_simulado_challenge_ordem"),
    )


# ---------------------------------------------------------------------------
# TEAMS / PARTICIPANTS
# ---------------------------------------------------------------------------
class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    aws_team_name = db.Column(db.String(150))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = db.relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    simulado_teams = db.relationship("SimuladoTeam", back_populates="team")

    def __repr__(self):
        return f"<Team {self.name}>"


class Participant(db.Model):
    __tablename__ = "participants"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    aws_identifier = db.Column(db.String(255))  # ex: "AWS-Skill-Builder_384c96d7-..."
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    team_memberships = db.relationship("TeamMember", back_populates="participant")
    challenge_solves = db.relationship("ChallengeSolver", back_populates="participant")

    def __repr__(self):
        return f"<Participant {self.name}>"


class TeamMember(db.Model):
    __tablename__ = "team_members"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    team_id = db.Column(db.BigInteger, db.ForeignKey("teams.id"), nullable=False)
    participant_id = db.Column(db.BigInteger, db.ForeignKey("participants.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship("Team", back_populates="members")
    participant = db.relationship("Participant", back_populates="team_memberships")

    __table_args__ = (
        db.UniqueConstraint("team_id", "participant_id", name="uk_team_member"),
    )


# ---------------------------------------------------------------------------
# SIMULADO_TEAMS  (resultado de uma equipe em um simulado)
# ---------------------------------------------------------------------------
class SimuladoTeam(db.Model):
    __tablename__ = "simulado_teams"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    simulado_id = db.Column(db.BigInteger, db.ForeignKey("simulados.id"), nullable=False)
    team_id = db.Column(db.BigInteger, db.ForeignKey("teams.id"), nullable=False)
    final_score = db.Column(db.Numeric(10, 2))
    final_rank = db.Column(db.Integer)
    number_challenges_solved = db.Column(db.SmallInteger)
    time_first_started_to_last_completion_seconds = db.Column(db.Integer)
    number_of_restarts_used = db.Column(db.SmallInteger)
    number_of_aws_accounts_used = db.Column(db.SmallInteger)
    number_of_support_chats_requested = db.Column(db.SmallInteger)
    suspected_of_cheating = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    simulado = db.relationship("Simulado", back_populates="simulado_teams")
    team = db.relationship("Team", back_populates="simulado_teams")
    challenge_results = db.relationship("TeamChallengeResult", back_populates="simulado_team", cascade="all, delete-orphan")
    services_used = db.relationship("TeamService", back_populates="simulado_team", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("simulado_id", "team_id", name="uk_simulado_team"),
    )

    def __repr__(self):
        return f"<SimuladoTeam simulado={self.simulado_id} team={self.team_id}>"


# ---------------------------------------------------------------------------
# TEAM_CHALLENGE_RESULTS  (desempenho de uma equipe em um JAM/challenge)
# ---------------------------------------------------------------------------
class TeamChallengeResult(db.Model):
    __tablename__ = "team_challenge_results"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    simulado_team_id = db.Column(db.BigInteger, db.ForeignKey("simulado_teams.id"), nullable=False)
    challenge_id = db.Column(db.BigInteger, db.ForeignKey("challenges.id"), nullable=False)
    status = db.Column(
        db.Enum("NOT_STARTED", "STARTED", "ATTEMPTED", "SOLVED", name="challenge_status"),
        nullable=False,
        default="NOT_STARTED",
    )
    num_completed_tasks = db.Column(db.SmallInteger)
    num_incorrect_answers = db.Column(db.SmallInteger)
    time_to_first_attempt_ms = db.Column(db.BigInteger)
    time_to_completed_challenge_ms = db.Column(db.BigInteger)
    num_clues_used = db.Column(db.SmallInteger)
    team_challenge_rating = db.Column(db.SmallInteger)
    team_challenge_difficulty_rating = db.Column(db.SmallInteger)
    total_number_of_attempts = db.Column(db.SmallInteger)
    learned_something_new = db.Column(db.Boolean)
    did_not_learn_something_new = db.Column(db.Boolean)
    feedback_comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    simulado_team = db.relationship("SimuladoTeam", back_populates="challenge_results")
    challenge = db.relationship("Challenge", back_populates="team_challenge_results")
    solvers = db.relationship("ChallengeSolver", back_populates="team_challenge_result", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("simulado_team_id", "challenge_id", name="uk_team_challenge_result"),
    )

    def __repr__(self):
        return f"<TeamChallengeResult team_result={self.simulado_team_id} challenge={self.challenge_id} status={self.status}>"


class ChallengeSolver(db.Model):
    __tablename__ = "challenge_solvers"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    team_challenge_result_id = db.Column(db.BigInteger, db.ForeignKey("team_challenge_results.id"), nullable=False)
    participant_id = db.Column(db.BigInteger, db.ForeignKey("participants.id"))
    aws_solver_identifier = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team_challenge_result = db.relationship("TeamChallengeResult", back_populates="solvers")
    participant = db.relationship("Participant", back_populates="challenge_solves")


# ---------------------------------------------------------------------------
# CHALLENGE_METRICS  (agregados por challenge dentro de um simulado)
# ---------------------------------------------------------------------------
class ChallengeMetric(db.Model):
    __tablename__ = "challenge_metrics"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    simulado_id = db.Column(db.BigInteger, db.ForeignKey("simulados.id"), nullable=False)
    challenge_id = db.Column(db.BigInteger, db.ForeignKey("challenges.id"), nullable=False)
    num_teams_started = db.Column(db.SmallInteger)
    num_teams_solved = db.Column(db.SmallInteger)
    num_teams_attempted = db.Column(db.SmallInteger)
    num_clues_requested = db.Column(db.SmallInteger)
    num_completed_tasks = db.Column(db.SmallInteger)
    num_incorrect_answers = db.Column(db.SmallInteger)
    avg_challenge_rank = db.Column(db.Numeric(8, 2))
    avg_challenge_difficulty = db.Column(db.Numeric(8, 2))
    challenge_feedback_count = db.Column(db.SmallInteger)
    learned_something_new = db.Column(db.SmallInteger)
    did_not_learn_something_new = db.Column(db.SmallInteger)
    time_to_first_attempt_min_ms = db.Column(db.BigInteger)
    time_to_first_attempt_max_ms = db.Column(db.BigInteger)
    time_to_first_attempt_mean_ms = db.Column(db.BigInteger)
    time_to_completed_min_ms = db.Column(db.BigInteger)
    time_to_completed_max_ms = db.Column(db.BigInteger)
    time_to_completed_mean_ms = db.Column(db.BigInteger)
    global_solve_time_min = db.Column(db.Integer)
    global_solve_time_max = db.Column(db.Integer)
    global_solve_time_mean = db.Column(db.Integer)
    number_of_restarts_used = db.Column(db.SmallInteger)
    total_number_of_aws_accounts_used = db.Column(db.SmallInteger)
    support_chat_requests = db.Column(db.SmallInteger)
    num_participants_used_aws_cli = db.Column(db.SmallInteger)
    num_participants_used_aws_console = db.Column(db.SmallInteger)
    num_participants_used_codewhisperer = db.Column(db.SmallInteger)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    simulado = db.relationship("Simulado", back_populates="challenge_metrics")
    challenge = db.relationship("Challenge", back_populates="challenge_metrics")
    services = db.relationship("ChallengeService", back_populates="challenge_metric", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("simulado_id", "challenge_id", name="uk_challenge_metrics"),
    )


# ---------------------------------------------------------------------------
# AWS_SERVICES  (catálogo de serviços AWS usados, N:N com metrics e teams)
# ---------------------------------------------------------------------------
class AwsService(db.Model):
    __tablename__ = "aws_services"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    service_name = db.Column(db.String(150), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AwsService {self.service_name}>"


class ChallengeService(db.Model):
    __tablename__ = "challenge_services"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    challenge_metric_id = db.Column(db.BigInteger, db.ForeignKey("challenge_metrics.id"), nullable=False)
    aws_service_id = db.Column(db.BigInteger, db.ForeignKey("aws_services.id"), nullable=False)

    challenge_metric = db.relationship("ChallengeMetric", back_populates="services")
    aws_service = db.relationship("AwsService")

    __table_args__ = (
        db.UniqueConstraint("challenge_metric_id", "aws_service_id", name="uk_challenge_service"),
    )


class TeamService(db.Model):
    __tablename__ = "team_services"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    simulado_team_id = db.Column(db.BigInteger, db.ForeignKey("simulado_teams.id"), nullable=False)
    aws_service_id = db.Column(db.BigInteger, db.ForeignKey("aws_services.id"), nullable=False)

    simulado_team = db.relationship("SimuladoTeam", back_populates="services_used")
    aws_service = db.relationship("AwsService")

    __table_args__ = (
        db.UniqueConstraint("simulado_team_id", "aws_service_id", name="uk_team_service"),
    )


# ---------------------------------------------------------------------------
# EVENT_FEEDBACK
# ---------------------------------------------------------------------------
class EventFeedback(db.Model):
    __tablename__ = "event_feedback"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    simulado_id = db.Column(db.BigInteger, db.ForeignKey("simulados.id"), nullable=False)
    event_rank = db.Column(db.SmallInteger)
    speaker_rank = db.Column(db.SmallInteger)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    simulado = db.relationship("Simulado", back_populates="event_feedback")
