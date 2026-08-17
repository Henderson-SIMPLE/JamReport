# JAM Report

Aplicação web para importar e consolidar relatórios JSON exportados dos
simulados/JAMs do **AWS Skill Builder**, guardando o histórico completo em
banco de dados e disponibilizando dashboards de acompanhamento (desempenho
por JAM, por equipe, catálogo de challenges, ranking de serviços AWS
utilizados, mapa de calor de datas, etc).

> Este projeto não depende de autenticação no AWS Skill Builder para
> consultar dados já importados — o fluxo é: rodar o simulado na AWS,
> exportar o JSON, subir no JAM Report, consultar pelo navegador quando quiser.

---

## Stack

| Camada       | Tecnologia                          |
|--------------|--------------------------------------|
| Backend      | Python 3.9 + Flask                   |
| ORM          | SQLAlchemy (via Flask-SQLAlchemy)    |
| Driver MySQL | PyMySQL                              |
| Banco        | MariaDB 11.4.x (também roda em MySQL 8+) |
| Frontend     | HTML + Bootstrap 5 (CDN) + Chart.js (CDN) |
| Servidor WSGI| Apache/mod_wsgi (produção) ou Flask dev server (local) |

Sem build step de frontend (sem npm/webpack) — as páginas são renderizadas
diretamente pelo Flask como HTML.

---

## Estrutura de pastas

```
jamreport/
├── app.py                     # ponto de entrada Flask, registra os blueprints
├── config.py                  # carrega variáveis do .env (DB, SECRET_KEY)
├── database.py                # instância única do SQLAlchemy (evita import circular)
├── requirements.txt           # dependências Python
├── .env.example                # modelo do .env (copiar e preencher, nunca commitar o real)
├── .gitignore
│
├── database/
│   ├── schema.sql              # DDL completo do banco (rodar uma vez na criação)
│   └── limpar_dados.sql        # TRUNCATE de todas as tabelas de dados (mantém a estrutura)
│
├── models/
│   └── __init__.py             # todas as classes SQLAlchemy (1:1 com schema.sql)
│
├── services/
│   ├── __init__.py
│   └── json_importer.py        # lógica central: parseia o JSON da AWS e grava no banco
│
└── routes/
    ├── __init__.py
    ├── import_routes.py        # telas e endpoints de upload (manual / automático / lote)
    ├── dashboard_routes.py     # visão geral, detalhe de simulado, catálogo de JAMs,
    │                           # ranking de serviços AWS, equipes
    └── dashboard_common.py     # layout compartilhado (navbar, CSS) e helpers de formatação
```

`models/`, `services/` e `routes/` são pacotes Python (têm `__init__.py`).
`routes/__init__.py` e `services/__init__.py` ficam vazios de propósito —
só existem pra marcar a pasta como pacote importável.

---

## Como rodar localmente

1. **Clonar o repositório e criar o ambiente virtual:**
   ```bash
   git clone <url-do-seu-repo>
   cd jamreport
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Criar o banco de dados** (MariaDB/MySQL) e rodar o schema:
   ```bash
   mysql -u seu_usuario -p seu_banco < database/schema.sql
   ```

3. **Configurar as variáveis de ambiente:**
   ```bash
   cp .env.example .env
   # edite o .env com host/usuário/senha/nome do banco reais
   ```

4. **Criar um usuário administrador mínimo** (necessário — ver seção
   "Sobre autenticação" abaixo):
   ```sql
   INSERT INTO users (username, full_name, password_hash, role, is_active)
   VALUES ('admin', 'Administrador', 'temporario', 'ADMIN', 1);
   ```

5. **Rodar a aplicação:**
   ```bash
   python3 app.py
   ```
   Acesse `http://127.0.0.1:5000/dashboard`.

---

## Sobre autenticação (importante ler antes de expor publicamente)

**Este projeto ainda não tem login implementado.** Toda importação é
gravada com `user_id=1` fixo (procure por `# TODO` no código) — a tabela
`users` do schema já está pronta para autenticação, mas login/senha e
controle de acesso ainda **não foram implementados**. Se você for hospedar
isso em um endereço público, qualquer pessoa com o link vê e importa dados.
Recomendado: manter atrás de uma URL não divulgada, VPN, ou implementar
autenticação antes de expor amplamente.

---

## Como funciona a importação — leia isto com atenção

### 1. Exportando o relatório da AWS

No AWS Skill Builder, ao final (ou durante) um simulado, é possível gerar
e baixar um relatório em JSON com as métricas do evento. Esse é o arquivo
que o JAM Report importa.

### 2. **A data do simulado — a parte mais importante**

O JSON exportado pela AWS **não contém a data em que o simulado foi
realizado**. Ele só traz `lastGeneratedDate`/`lastUpdatedDate`, que é a
data em que **o relatório foi gerado/clicado na plataforma** — não a data
do treinamento em si. Se você gerar o relatório dias depois do simulado
acontecer, essa data fica errada.

**Por isso, a forma confiável de informar a data certa é renomear o
arquivo baixado antes de subir**, seguindo este padrão:

```
qualquercoisa-DDMMAAAA.json
```

Os últimos 8 dígitos antes de `.json` são interpretados como
dia/mês/ano. Exemplos válidos:

```
Simulado_JAM-13082026.json   →  13/08/2026
relatorio_20062026.json      →  20/06/2026
13082026.json                 →  13/08/2026
```

O importador prioriza essa data (extraída do nome do arquivo) sobre
qualquer coisa vinda do conteúdo do JSON. Se o arquivo não seguir esse
padrão, ele cai no fallback de `lastGeneratedDate`/`lastUpdatedDate` — e
nesse caso a tela mostra um selo amarelo "estimada" no dashboard, avisando
que aquela data pode estar incorreta (contra o selo verde "nome do
arquivo", que indica data confiável).

Se dois arquivos caírem na mesma data (ex: dois simulados diferentes no
mesmo dia), o sistema gera automaticamente um sufixo de versão
(`...2026`, `...2026b`, `...2026c`...) para não colidir.

### 3. O que é extraído automaticamente do próprio relatório (sem precisar informar nada)

Diferente da data, estes dados **vêm prontos de dentro do JSON** e não
precisam de nenhuma ação manual:

- **Nome da equipe** (`teamMetrics[].teamName`).
- **Membros da equipe** (`teamMetrics[].teamMembers`) — atenção: o JSON só
  traz o *nome* do membro aqui, sem um identificador único da AWS; o
  identificador único (`AWS-Skill-Builder_...`) só aparece depois, dentro
  de `teamMembersSolved`, quando essa pessoa efetivamente resolve um
  challenge. Por isso é possível (embora raro) o mesmo participante gerar
  dois registros diferentes no banco, um por cada "fonte" de identificação.
- **JAMs (challenges) do simulado** e seus títulos (`challengeTitles`).
- **Status de cada JAM por equipe** — o JSON não tem um campo `status`
  explícito; o importador infere:
  - `SOLVED` se a lista `teamMembersSolved` daquele challenge não estiver vazia
    (esse é um dado que a própria AWS calcula, não uma estimativa nossa).
  - `ATTEMPTED` se `totalNumberOfAttempts > 0` mas ninguém resolveu.
  - `STARTED` se está na lista `startedChallenges` mas sem tentativa registrada.
  - `NOT_STARTED` se está na lista `notStartedChallenges`.
- **Quantidade de tarefas concluídas por JAM** (`numCompletedTasks`) — importante:
  a AWS **não informa o total de tarefas de cada JAM**, só quantas foram
  concluídas. Cada JAM tem uma quantidade própria e não padronizada de
  tarefas, então esse número não é comparável entre JAMs diferentes (um
  JAM "resolvido" com 1 tarefa concluída e outro "resolvido" com 4 tarefas
  concluídas estão ambos corretos — só têm quantidades de tarefas
  diferentes; a AWS não expõe o total pra calcular um "3 de 4", por exemplo).
- **Dicas usadas, reinicializações, tentativas, tempo até resolver, contas
  AWS usadas, uso de CLI/Console/CodeWhisperer, chats de suporte pedidos,
  suspeita de fraude (`suspectedOfCheating`)** — todos vêm prontos do JSON.
- **Serviços AWS utilizados** por challenge e por equipe
  (`awsServicesUsed`), usados no ranking de serviços do dashboard.

### 4. Duplicidade

Cada arquivo é identificado por hash SHA-256 do conteúdo — o mesmo arquivo
não pode ser importado duas vezes (mensagem de erro clara ao tentar). Já
um nome de simulado duplicado (dois arquivos diferentes apontando pra
mesma data/nome) também é bloqueado, a menos que o sufixo de versão
automático resolva o conflito (ver seção 2).

### 5. Três formas de importar

- **`/importar`** — nome do simulado digitado manualmente (não depende do
  nome do arquivo).
- **`/importar/auto`** — um arquivo por vez, nome/data 100% automáticos
  (segue as regras da seção 2).
- **`/importar/lote`** — vários arquivos de uma vez, todos automáticos;
  um arquivo com problema não impede os demais de importarem, e o
  resultado de cada um aparece numa tabela ao final.

---

## Peculiaridades de hospedagem (se for usar KingHost ou hospedagem similar)

Estas notas vieram de problemas reais enfrentados ao hospedar este projeto
na KingHost — podem não se aplicar a outros provedores, mas ficam
registradas caso ajudem:

- **Erro 1045 (access denied) mesmo com senha e grants corretos**: em
  alguns provedores, o usuário "padrão" criado junto com o banco não tem
  permissão de fato — é necessário criar um usuário novo explicitamente e
  conceder os grants (`INSERT`, `SELECT`, `UPDATE`, `DELETE`, etc) a ele.
- **Aplicações Python em hospedagem compartilhada por vezes só suportam
  binding em subdiretório** (`seudominio.com/nome_app`), não em subdomínio
  dedicado — verifique isso antes de planejar a URL final.
- **`.env` não encontrado em produção mas funciona no terminal**: o
  diretório de trabalho do processo WSGI é diferente do diretório do
  terminal SSH. Sempre carregue o `.env` com caminho absoluto baseado em
  `os.path.dirname(os.path.abspath(__file__))` (já implementado em
  `config.py` deste projeto).
- **Sem botão de "reiniciar aplicação" no painel**: rode
  `touch caminho/para/seuapp.wsgi` — isso força o Apache/mod_wsgi a
  recarregar o processo Python.
- **`NULLS LAST` não existe no MariaDB/MySQL** (é sintaxe PostgreSQL/Oracle).
  Para ordenar com nulos por último em qualquer banco, use:
  ```python
  .order_by(Coluna.is_(None), Coluna.asc())
  ```
- **`str.format()` quebra com CSS**: qualquer `{ }` de CSS dentro de uma
  string formatada com `.format()` é interpretado como placeholder e
  quebra. Use `.replace("{chave}", valor)` para montar HTML com CSS embutido.
- **Duplicatas dentro do próprio JSON de origem**: `teamMetrics[].awsServicesUsed`
  pode repetir o mesmo serviço; sempre verifique existência antes de
  inserir em tabelas de junção (`TeamService`, `ChallengeService`) para
  evitar `IntegrityError` de chave única.

---

## Licença / uso

Projeto pessoal/educacional, sem licença definida ainda — ajuste conforme
sua intenção de divulgação (MIT costuma ser uma escolha simples e permissiva
se o objetivo é só compartilhar com amigos e permitir que outros usem/adaptem).
