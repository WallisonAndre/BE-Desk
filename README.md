<p align="center">
  <img src="https://img.shields.io/badge/BE_Desk-Gestão_e_Reservas-007BFF?style=for-the-badge&logo=basketball" alt="BE-Desk Banner">
</p>

<h1 align="center">🏀 BE-Desk 📋</h1>

<p align="center">
  <strong>Organização e praticidade ao seu alcance.</strong><br>
  Sistema online de reserva de espaços e organização de eventos do Bloco E do IFRN.
</p>

---

## 📖 Sobre o Projeto

O **BE-Desk** nasceu para modernizar e digitalizar o uso dos espaços do Bloco E do IFRN — quadra, ginásio e salas —, tanto nas reservas do dia a dia quanto nos eventos abertos à comunidade acadêmica.

Combinamos a necessidade de um controle interno rigoroso com a facilidade de acesso para alunos e servidores. O sistema substitui os antigos registros manuais por uma plataforma digital, com login pela conta institucional do SUAP.

### 🚀 Funcionalidades Principais
- [x] **Reserva de Espaços:** Pedido de horário na grade da sala, com aprovação pela administração.
- [x] **Grade de Horários:** Visualização por sala e por semana, mostrando o que já está ocupado.
- [x] **Eventos:** Atividades esportivas, acadêmicas e institucionais com inscrição de participantes e limite de vagas. O evento reserva o espaço automaticamente e bloqueia conflitos.
- [x] **Login Institucional:** Autenticação pelo SUAP, sem senha separada.
- [x] **Notificações:** Avisos de aprovação, recusa e mudança em reservas e eventos.
- [x] **Blog:** Publicações e comunicados do bloco.
- [x] **Painel Administrativo:** Aprovação de pedidos, gestão de salas e permissões.

---

## 🛠 Tecnologias Utilizadas

As principais ferramentas usadas no desenvolvimento do sistema:

- [**Python / Django**](https://www.djangoproject.com/) - Core do sistema, lógica de negócio e painel administrativo.
- [**HTML5 / CSS3 / JavaScript**](https://developer.mozilla.org/pt-BR/) - Interface responsiva para dispositivos móveis e desktops.
- [**SQLite**](https://www.sqlite.org/index.html) / [**PostgreSQL**](https://www.postgresql.org/) - Banco de dados: SQLite em desenvolvimento, PostgreSQL em produção.
- [**Docker / Nginx**](https://www.docker.com/) - Containerização e servidor para deploys robustos e seguros.

---

<h2 align="center">🚀 Como Executar o Projeto</h2>

<p align="center">
  Siga os passos abaixo para configurar e iniciar o <strong>BE-Desk</strong> em ambiente de desenvolvimento.
</p>

<br>

### 📦 1. Clone o repositório

```bash
git clone https://github.com/WallisonAndre/BE-Desk.git
cd BE-Desk
```

### 🐍 2. Crie um ambiente virtual

```bash
python -m venv venv
```

### ▶️ 3. Ative o ambiente virtual

**Windows (PowerShell/CMD):**

```bash
.\venv\Scripts\activate
```

**Linux/macOS:**

```bash
source venv/bin/activate
```

### 📥 4. Instale as dependências

```bash
pip install -r requirements.txt
```

### ⚙️ 5. Configure as variáveis de ambiente

Copie o arquivo de exemplo e preencha com as credenciais da aplicação OAuth2 do SUAP:

```bash
cp .env.example .env
```

```text
SUAP_OAUTH_CLIENT_ID=seu_client_id
SUAP_OAUTH_CLIENT_SECRET=seu_client_secret
SUAP_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback/
SUAP_API_URL=https://suap.ifrn.edu.br
```

> ⚠️ O `SUAP_OAUTH_REDIRECT_URI` precisa ser **idêntico** ao cadastrado na aplicação no SUAP, incluindo a barra final. Qualquer diferença resulta em `Mismatching redirect URI` na hora de entrar.

O sistema sobe sem o `.env` — apenas o login pelo SUAP fica indisponível.

### 🗄️ 6. Configure o banco de dados

```bash
python manage.py makemigrations
python manage.py migrate
```

### ▶️ 7. Inicie o servidor

```bash
python manage.py runserver
```

### 🌐 8. Acesse o sistema

Abra o navegador e acesse:

```text
http://127.0.0.1:8000/
```


---

## 📂 Estrutura do Projeto

O BE-Desk é um projeto **Django** dividido em apps por domínio. Os modelos do núcleo ficam concentrados em `bedesk`, e os demais apps trazem as regras, as rotas e as telas de cada parte do sistema.

```text
BE-Desk/
├── config/              # settings, urls raiz, wsgi e asgi do projeto
│
├── bedesk/              # modelos do núcleo: Sala, Agendamento e Profile
├── core/                # página inicial e painel administrativo
├── usuarios/            # login, cadastro, perfil e permissões
├── reservas/            # locais, grade de horários e pedido de reserva
├── eventos/             # eventos nos espaços, com inscrição de participantes
├── notificacoes/        # notificações internas (sino e listagem)
├── blog/                # publicações e administração do blog
├── integracao_suap/     # autenticação OAuth2 com o SUAP
├── relatorios/          # app reservado para relatórios (ainda sem rotas)
│
├── templates/           # templates HTML, uma pasta por app
├── static/              # css, js e imagens
├── media/               # arquivos enviados pelos usuários
├── docs/                # diagramas e protótipos
│
├── nginx/               # configuração do servidor
├── Dockerfile           # imagem da aplicação
├── docker-compose.yml   # orquestração dos containers
├── entrypoint.sh        # script de inicialização do container
├── manage.py            # utilitário de linha de comando do Django
└── requirements.txt     # dependências Python
```

### Como os apps se organizam

O `bedesk` guarda os modelos usados por todo o sistema e não tem rotas próprias. Quem expõe as telas de sala e reserva é o `reservas`, e quem expõe o painel do administrador é o `core`. Já `eventos`, `notificacoes` e `blog` são autocontidos: têm modelo, rotas e telas próprios.

Onde a quantidade de telas justifica, as views ficam em pacote em vez de arquivo único:

```text
reservas/views/     salas.py, reservas.py, ajax.py
core/views/         public.py (site), dashboard.py (administração)
eventos/views/      eventos.py
notificacoes/services/   notificar.py — funções que disparam as notificações
eventos/services.py      ocupa e libera a grade de horários do evento
```

---

## 🌿 Branches e Fluxo de Trabalho

O repositório usa uma branch de integração entre o trabalho do dia a dia e a versão estável:

| Branch | Papel |
| --- | --- |
| `main` | Versão estável. Só recebe código que já passou pela `development`. |
| `development` | Integração do time. É a base de toda tarefa nova. |
| `feat/…` `fix/…` `chore/…` | Uma branch por tarefa, criada a partir da `development`. |

### Prefixos

O mesmo vocabulário vale para o nome da branch e para a mensagem do commit:

- `feat:` funcionalidade nova
- `fix:` correção de comportamento
- `refactor:` reorganização interna, sem mudança de funcionalidade
- `chore:` manutenção do repositório e configuração
- `task:` tarefa técnica que não é erro nem funcionalidade

### Ciclo de uma tarefa

```bash
# 1. parta da development atualizada
git checkout development
git pull

# 2. crie a branch da tarefa
git checkout -b feat/nome-da-tarefa

# 3. faça os commits
git commit -m "feat: descreve o que passou a existir"

# 4. publique a branch
git push -u origin feat/nome-da-tarefa

# 5. abra o Pull Request apontando para a development
gh pr create --base development
```

> ⚠️ A branch padrão do repositório ainda é a `main`. Enquanto for assim, o `--base development` é obrigatório — sem ele o Pull Request nasce apontando para a `main`.

### Commits

O assunto vai em uma linha curta, no imperativo e com o prefixo da tabela acima. Quando a mudança não é óbvia, o corpo do commit explica **por que** ela foi feita, não o que o diff já mostra.

### Issues

As issues são abertas pelos formulários em `.github/ISSUE_TEMPLATE`:

| Formulário | Label | Quando usar |
| --- | --- | --- |
| Funcionalidade | `enhancement` | funcionalidade ou melhoria percebida pelo usuário |
| Bug | `bug` | erro ou comportamento inesperado do sistema |
| Tarefa técnica | `task` | atividade técnica que não é bug nem funcionalidade |

### Quadro de Acompanhamento

O andamento das tarefas fica no Project **[BE-Desk](https://github.com/users/devigMurilo/projects/2)**, onde cada issue é acompanhada pelas colunas `Backlog`, `Sprint Backlog (To do)`, `In Progress`, `In Review` e `Done`.
