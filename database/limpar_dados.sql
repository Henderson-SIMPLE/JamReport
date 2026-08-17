-- JAM REPORT - LIMPEZA DE DADOS (mantém a estrutura das tabelas)
-- Execute conectado ao banco simple01.
-- Ordem respeitando dependências de FK (tabelas "filhas" primeiro).

SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE challenge_solvers;
TRUNCATE TABLE challenge_services;
TRUNCATE TABLE team_services;
TRUNCATE TABLE challenge_metrics;
TRUNCATE TABLE team_challenge_results;
TRUNCATE TABLE simulado_teams;
TRUNCATE TABLE team_members;
TRUNCATE TABLE participants;
TRUNCATE TABLE teams;
TRUNCATE TABLE simulado_challenges;
TRUNCATE TABLE challenges;
TRUNCATE TABLE event_feedback;
TRUNCATE TABLE simulados;
TRUNCATE TABLE imported_files;
TRUNCATE TABLE aws_services;

-- users fica de fora do TRUNCATE de propósito, pra não perder o admin.
-- Se quiser limpar até isso, descomente a linha abaixo:
-- TRUNCATE TABLE users;

SET FOREIGN_KEY_CHECKS = 1;

-- Confirma que o usuário admin (id=1) ainda existe (ele é referenciado por
-- imported_files.imported_by_user_id no importador). Se o SELECT abaixo não
-- retornar nada, recrie com o INSERT comentado em seguida.
SELECT id, username FROM users WHERE id = 1;

-- INSERT INTO users (username, full_name, password_hash, role, is_active)
-- VALUES ('admin', 'Administrador', 'temporario', 'ADMIN', 1);
