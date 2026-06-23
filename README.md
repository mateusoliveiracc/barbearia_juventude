# Barbearia Juventude — Sistema de Agendamento

Site completo para a barbearia, com página inicial institucional, agendamento
online para clientes e painel administrativo para gerenciar os horários.

Feito em **Python + Flask**, com banco de dados **SQLite** (não precisa instalar
nenhum banco separado — é só um arquivo `barbearia.db` que é criado automaticamente).

---

## Como abrir no PyCharm

1. Abra a pasta `barbearia` no PyCharm como um novo projeto.
2. Crie um ambiente virtual (o PyCharm geralmente sugere isso automaticamente
   na primeira vez que você abre um projeto Python). Se não sugerir:
   - `File > Settings > Project > Python Interpreter > Add Interpreter > Add Local Interpreter`
   - Escolha "Virtualenv Environment" e confirme.
3. Abra o terminal do PyCharm (aba "Terminal" na parte inferior) e rode:
   ```
   pip install -r requirements.txt
   ```
4. Rode o arquivo `app.py` (botão verde de play, ou `python app.py` no terminal).
5. O terminal vai mostrar algo como:
   ```
   Servicos iniciais cadastrados.
   Admin criado -> usuario: admin | senha: barbearia123
   * Running on http://127.0.0.1:5000
   ```
6. Acesse **http://127.0.0.1:5000** no navegador. Pronto, o site está rodando!

Na primeira execução, o sistema cria o arquivo `barbearia.db` automaticamente,
já populado com os 17 serviços da barbearia e um usuário admin padrão.

---

## Acessos

### Site (cliente)
- Início: `http://127.0.0.1:5000/`
- Agendar: `http://127.0.0.1:5000/agendar`

### Painel administrativo
- Login: `http://127.0.0.1:5000/admin/login`
- **Usuário padrão:** `admin`
- **Senha padrão:** `barbearia123`

> ⚠️ **Importante:** troque essas credenciais antes de publicar o site para o
> público. Veja a seção "Trocar usuário/senha do admin" abaixo.

No painel você pode:
- Ver os agendamentos por dia (com filtro de data e de barbeiro)
- Cancelar, reativar ou excluir agendamentos
- Ver os próximos 5 agendamentos futuros
- Ativar/desativar serviços ou cadastrar novos serviços
- Ativar/desativar barbeiros ou cadastrar novos barbeiros

---

## Estrutura do projeto

```
barbearia/
├── app.py                  ← toda a lógica do site (rotas, banco, regras de horário)
├── requirements.txt        ← dependências (só Flask e Werkzeug)
├── barbearia.db            ← banco de dados (criado automaticamente na 1ª execução)
├── static/
│   └── css/style.css       ← visual do site (tema escuro + dourado)
└── templates/
    ├── base.html                ← layout base das páginas públicas
    ├── index.html                ← página inicial (institucional)
    ├── agendar.html              ← formulário de agendamento
    ├── confirmado.html           ← página de confirmação
    ├── admin_base.html           ← layout base do admin
    ├── admin_login.html          ← login do admin
    ├── admin_dashboard.html      ← lista de agendamentos
    ├── admin_servicos.html       ← lista de serviços
    ├── admin_novo_servico.html   ← cadastro de novo serviço
    ├── admin_barbeiros.html      ← lista de barbeiros
    └── admin_novo_barbeiro.html  ← cadastro de novo barbeiro
```

---

## Como funciona o agendamento

- Os horários de funcionamento estão configurados no topo do `app.py`,
  na variável `HORARIO_FUNCIONAMENTO` (já preenchidos com os horários reais
  da Barbearia Juventude).
- Os horários disponíveis para escolha são gerados em intervalos de **30 minutos**.
- O cliente escolhe obrigatoriamente um **barbeiro** ao agendar. Cada barbeiro
  tem sua própria agenda — se o João está ocupado às 10h, o Carlos pode estar
  livre nesse mesmo horário.
- Quando o cliente escolhe um serviço, o sistema calcula a duração dele e
  **bloqueia automaticamente** os horários daquele barbeiro específico que
  conflitariam com outro agendamento já existente dele.
- Datas e horários que já passaram não aparecem como opção.

## Como editar os barbeiros

1. **Pelo painel admin** (`/admin/barbeiros`) — adicionar, ativar/desativar.
2. **Direto no código**, editando a lista `BARBEIROS_INICIAIS` no `app.py`
   — só afeta a **primeira execução** (quando o banco é criado do zero).

Se você já tinha o site rodando antes dessa atualização (com agendamentos
salvos), não se preocupe: ao rodar o `app.py` pela primeira vez após essa
atualização, o sistema detecta o banco antigo e faz uma migração automática,
criando a coluna de barbeiro e associando todos os agendamentos já existentes
ao primeiro barbeiro cadastrado. Nenhum dado é perdido.

---

## Como editar as informações da empresa

Tudo que aparece na página inicial (endereço, telefone, Instagram, horários,
formas de pagamento) está centralizado no topo do `app.py`, no dicionário
`EMPRESA` e na variável `HORARIO_FUNCIONAMENTO`. Não precisa tocar no HTML
para alterar esses dados.

```python
EMPRESA = {
    "nome": "Barbearia Juventude",
    "nota": "5.0",
    "endereco": "...",
    "telefone": "(31) 98268-6431",
    ...
}
```

## Como editar os serviços

Os serviços podem ser editados de duas formas:
1. **Pelo painel admin** (`/admin/servicos`) — adicionar, ativar/desativar.
2. **Direto no código**, editando a lista `SERVICOS_INICIAIS` no `app.py`
   — mas isso só afeta a **primeira execução** (quando o banco é criado).
   Depois disso, use o painel admin.

---

## Trocar usuário/senha do admin

A forma mais simples: apague o arquivo `barbearia.db`, defina variáveis de
ambiente antes de rodar o `app.py`, e rode de novo (isso recria o banco do
zero com os novos dados):

No terminal do PyCharm:
```bash
# Windows (PowerShell)
$env:ADMIN_USER="seu_usuario"
$env:ADMIN_PASS="sua_senha_forte"
python app.py

# Mac/Linux
export ADMIN_USER="seu_usuario"
export ADMIN_PASS="sua_senha_forte"
python app.py
```

⚠️ Apagar o `barbearia.db` também apaga os agendamentos e serviços já
cadastrados. Se já tiver dados reais, prefira criar um segundo usuário
direto no banco ou me peça uma rota de "trocar senha" pelo próprio painel.

---

## Publicar o site na internet (próximos passos)

Esse projeto roda localmente (no seu computador) por padrão. Para os clientes
acessarem pela internet, você vai precisar hospedar em um serviço como
Render, Railway, PythonAnywhere ou similar. Quando chegar nessa etapa, me
chame que te ajudo a configurar — o processo muda dependendo do serviço
escolhido.
