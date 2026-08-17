-- JAM REPORT - SCHEMA V1
-- Banco: simple01
-- SGBD: MariaDB 11.4.x
-- Execute conectado ao banco simple01.
-- A senha do ADMIN da aplicacao sera criada pelo backend como hash seguro.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS challenge_solvers;
DROP TABLE IF EXISTS challenge_services;
DROP TABLE IF EXISTS team_services;
DROP TABLE IF EXISTS challenge_metrics;
DROP TABLE IF EXISTS team_challenge_results;
DROP TABLE IF EXISTS simulado_teams;
DROP TABLE IF EXISTS team_members;
DROP TABLE IF EXISTS participants;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS simulado_challenges;
DROP TABLE IF EXISTS challenges;
DROP TABLE IF EXISTS event_feedback;
DROP TABLE IF EXISTS simulados;
DROP TABLE IF EXISTS imported_files;
DROP TABLE IF EXISTS aws_services;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('ADMIN','USER') NOT NULL DEFAULT 'USER',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_username (username),
    UNIQUE KEY uk_users_email (email),
    KEY idx_users_role (role),
    KEY idx_users_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE imported_files (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    original_filename VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT UNSIGNED NULL,
    sha256 CHAR(64) NOT NULL,
    mime_type VARCHAR(100) NULL,
    raw_json LONGTEXT NOT NULL,
    imported_by_user_id BIGINT UNSIGNED NOT NULL,
    imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_imported_files_sha256 (sha256),
    KEY idx_imported_files_user (imported_by_user_id),
    CONSTRAINT fk_imported_files_user FOREIGN KEY (imported_by_user_id)
        REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE simulados (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nome VARCHAR(150) NOT NULL,
    nome_base VARCHAR(100) NULL,
    data_simulado DATE NOT NULL,
    versao CHAR(1) NOT NULL DEFAULT 'A',
    descricao TEXT NULL,
    criado_em_aws DATETIME NULL,
    inicio_programado DATETIME NULL,
    fim_programado DATETIME NULL,
    duracao_programada_segundos INT UNSIGNED NULL,
    quantidade_jams SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    event_name VARCHAR(100) NULL,
    last_updated_aws DATETIME NULL,
    last_generated_aws DATETIME NULL,
    imported_file_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_simulado_nome (nome),
    KEY idx_simulado_data (data_simulado),
    KEY idx_simulado_versao (data_simulado, versao),
    KEY idx_simulado_imported_file (imported_file_id),
    CONSTRAINT fk_simulado_imported_file FOREIGN KEY (imported_file_id)
        REFERENCES imported_files(id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE challenges (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    aws_challenge_id VARCHAR(150) NOT NULL,
    title VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_challenges_aws_id (aws_challenge_id),
    KEY idx_challenges_title (title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE simulado_challenges (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    simulado_id BIGINT UNSIGNED NOT NULL,
    challenge_id BIGINT UNSIGNED NOT NULL,
    ordem SMALLINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_simulado_challenge (simulado_id, challenge_id),
    UNIQUE KEY uk_simulado_challenge_ordem (simulado_id, ordem),
    KEY idx_sc_challenge (challenge_id),
    CONSTRAINT fk_sc_simulado FOREIGN KEY (simulado_id)
        REFERENCES simulados(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_sc_challenge FOREIGN KEY (challenge_id)
        REFERENCES challenges(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE teams (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    aws_team_name VARCHAR(150) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_team_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE participants (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    aws_identifier VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_participant_name (name),
    KEY idx_participant_aws (aws_identifier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_members (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    team_id BIGINT UNSIGNED NOT NULL,
    participant_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_team_member (team_id, participant_id),
    CONSTRAINT fk_team_members_team FOREIGN KEY (team_id)
        REFERENCES teams(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_team_members_participant FOREIGN KEY (participant_id)
        REFERENCES participants(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE simulado_teams (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    simulado_id BIGINT UNSIGNED NOT NULL,
    team_id BIGINT UNSIGNED NOT NULL,
    final_score DECIMAL(10,2) NULL,
    final_rank INT UNSIGNED NULL,
    number_challenges_solved SMALLINT UNSIGNED NULL,
    time_first_started_to_last_completion_seconds INT UNSIGNED NULL,
    number_of_restarts_used SMALLINT UNSIGNED NULL,
    number_of_aws_accounts_used SMALLINT UNSIGNED NULL,
    number_of_support_chats_requested SMALLINT UNSIGNED NULL,
    suspected_of_cheating TINYINT(1) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_simulado_team (simulado_id, team_id),
    KEY idx_st_team (team_id),
    CONSTRAINT fk_st_simulado FOREIGN KEY (simulado_id)
        REFERENCES simulados(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_st_team FOREIGN KEY (team_id)
        REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_challenge_results (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    simulado_team_id BIGINT UNSIGNED NOT NULL,
    challenge_id BIGINT UNSIGNED NOT NULL,
    status ENUM('NOT_STARTED','STARTED','ATTEMPTED','SOLVED') NOT NULL DEFAULT 'NOT_STARTED',
    num_completed_tasks SMALLINT UNSIGNED NULL,
    num_incorrect_answers SMALLINT UNSIGNED NULL,
    time_to_first_attempt_ms BIGINT UNSIGNED NULL,
    time_to_completed_challenge_ms BIGINT UNSIGNED NULL,
    num_clues_used SMALLINT UNSIGNED NULL,
    team_challenge_rating TINYINT UNSIGNED NULL,
    team_challenge_difficulty_rating TINYINT UNSIGNED NULL,
    total_number_of_attempts SMALLINT UNSIGNED NULL,
    learned_something_new TINYINT(1) NULL,
    did_not_learn_something_new TINYINT(1) NULL,
    feedback_comments TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_team_challenge_result (simulado_team_id, challenge_id),
    KEY idx_tcr_challenge (challenge_id),
    KEY idx_tcr_status (status),
    CONSTRAINT fk_tcr_simulado_team FOREIGN KEY (simulado_team_id)
        REFERENCES simulado_teams(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_tcr_challenge FOREIGN KEY (challenge_id)
        REFERENCES challenges(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE challenge_solvers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    team_challenge_result_id BIGINT UNSIGNED NOT NULL,
    participant_id BIGINT UNSIGNED NULL,
    aws_solver_identifier VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_cs_result (team_challenge_result_id),
    KEY idx_cs_participant (participant_id),
    CONSTRAINT fk_cs_result FOREIGN KEY (team_challenge_result_id)
        REFERENCES team_challenge_results(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cs_participant FOREIGN KEY (participant_id)
        REFERENCES participants(id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE challenge_metrics (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    simulado_id BIGINT UNSIGNED NOT NULL,
    challenge_id BIGINT UNSIGNED NOT NULL,
    num_teams_started SMALLINT UNSIGNED NULL,
    num_teams_solved SMALLINT UNSIGNED NULL,
    num_teams_attempted SMALLINT UNSIGNED NULL,
    num_clues_requested SMALLINT UNSIGNED NULL,
    num_completed_tasks SMALLINT UNSIGNED NULL,
    num_incorrect_answers SMALLINT UNSIGNED NULL,
    avg_challenge_rank DECIMAL(8,2) NULL,
    avg_challenge_difficulty DECIMAL(8,2) NULL,
    challenge_feedback_count SMALLINT UNSIGNED NULL,
    learned_something_new SMALLINT UNSIGNED NULL,
    did_not_learn_something_new SMALLINT UNSIGNED NULL,
    time_to_first_attempt_min_ms BIGINT UNSIGNED NULL,
    time_to_first_attempt_max_ms BIGINT UNSIGNED NULL,
    time_to_first_attempt_mean_ms BIGINT UNSIGNED NULL,
    time_to_completed_min_ms BIGINT UNSIGNED NULL,
    time_to_completed_max_ms BIGINT UNSIGNED NULL,
    time_to_completed_mean_ms BIGINT UNSIGNED NULL,
    global_solve_time_min INT UNSIGNED NULL,
    global_solve_time_max INT UNSIGNED NULL,
    global_solve_time_mean INT UNSIGNED NULL,
    number_of_restarts_used SMALLINT UNSIGNED NULL,
    total_number_of_aws_accounts_used SMALLINT UNSIGNED NULL,
    support_chat_requests SMALLINT UNSIGNED NULL,
    num_participants_used_aws_cli SMALLINT UNSIGNED NULL,
    num_participants_used_aws_console SMALLINT UNSIGNED NULL,
    num_participants_used_codewhisperer SMALLINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_challenge_metrics (simulado_id, challenge_id),
    CONSTRAINT fk_cm_simulado FOREIGN KEY (simulado_id)
        REFERENCES simulados(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cm_challenge FOREIGN KEY (challenge_id)
        REFERENCES challenges(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE aws_services (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    service_name VARCHAR(150) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_aws_service_name (service_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE challenge_services (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    challenge_metric_id BIGINT UNSIGNED NOT NULL,
    aws_service_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_challenge_service (challenge_metric_id, aws_service_id),
    CONSTRAINT fk_challenge_services_metric FOREIGN KEY (challenge_metric_id)
        REFERENCES challenge_metrics(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_challenge_services_service FOREIGN KEY (aws_service_id)
        REFERENCES aws_services(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_services (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    simulado_team_id BIGINT UNSIGNED NOT NULL,
    aws_service_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_team_service (simulado_team_id, aws_service_id),
    CONSTRAINT fk_team_services_team FOREIGN KEY (simulado_team_id)
        REFERENCES simulado_teams(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_team_services_service FOREIGN KEY (aws_service_id)
        REFERENCES aws_services(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE event_feedback (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    simulado_id BIGINT UNSIGNED NOT NULL,
    event_rank TINYINT UNSIGNED NULL,
    speaker_rank TINYINT UNSIGNED NULL,
    notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_event_feedback_simulado FOREIGN KEY (simulado_id)
        REFERENCES simulados(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- FIM DO SCHEMA V1
