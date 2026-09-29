# cvcrm-ferramentas

Scripts em Python para manutenção de leads em massa no **CV CRM**, usando a API
pública (v1 e CVDW) e, quando a API não alcança, o painel web autenticado.

Nasceram de três incidentes reais:

| caso | problema | pasta |
|---|---|---|
| **Restaurar nomes** | uma integração sobrescreveu o nome de centenas de leads com "Sem nome" | `scripts/restaurar_nomes/` |
| **Limpeza "Sem nome"** | classificar leads sem nome: restaurar o nome, descartar por inatividade, ou não mexer | `scripts/limpeza_sem_nome/` |
| **Importar planilha** | leads de um formulário do Meta não chegaram ao CV; importar sem passar pela roleta | `scripts/importar_leads/` |

## Instalação

```bash
pip install -r requirements.txt
cp config.exemplo.json config.json   # e preencha
```

Os scripts rodam como módulos, a partir da raiz do repositório:

```bash
python -m scripts.restaurar_nomes.testar_um <idlead>
```

Cada script trabalha dentro de `dados/<caso>/`, que é criado sozinho e **nunca é versionado**.

## Configuração

Tudo que é específico da empresa fica no `config.json`, que está no `.gitignore`:

- `dominio`, `email`, `token` — credenciais de API de um usuário **Gestor**
- `limpeza` — situações que podem ir para descartado, prazo de inatividade, regex dos autores que são
  integrações automáticas, e o motivo de cancelamento por situação
- `importacao` — imobiliária, empreendimento, mídia e conversão de destino

Veja `config.exemplo.json`.

Para os scripts que leem o painel web (histórico do lead), cole na raiz um `curl.txt` com o
**Copy as cURL (bash)** de qualquer página do painel aberta com login (F12 → Network → botão
direito na requisição). Confira com `python -m scripts.checar_sessao <idlead>`.

## Fluxo de trabalho

Todo script que escreve no CRM roda em **simulação** por padrão e só grava com `--executar`.
O padrão que seguimos sempre:

1. gerar um plano em CSV e revisar à mão;
2. `--executar --limite 1` e conferir o lead no painel;
3. rodar o lote;
4. rodar o `conferir`, que relê cada lead na API e compara com o plano.

Os scripts de lote salvam o progresso e retomam de onde pararam.

### Restaurar nomes

```bash
python -m scripts.restaurar_nomes.extrair_ids <planilha_do_painel.xlsx>
python -m scripts.restaurar_nomes.historico_nomes --todos      # lê o histórico no painel
python -m scripts.restaurar_nomes.coletar atual
python -m scripts.restaurar_nomes.plano
python -m scripts.restaurar_nomes.aplicar --executar --limite 3
python -m scripts.restaurar_nomes.conferir
```

### Limpeza "Sem nome"

```bash
python -m scripts.limpeza_sem_nome.listar_sem_nome       # varre a base inteira no CVDW
python -m scripts.limpeza_sem_nome.classificar           # lê o histórico e decide a ação
python -m scripts.limpeza_sem_nome.aplicar --executar --acao descartar --situacao 1 --limite 1
python -m scripts.limpeza_sem_nome.aplicar --executar
python -m scripts.limpeza_sem_nome.conferir
```

Regras (`cvcrm/regras.py`), em ordem:

1. situação na lista de descartáveis **e** sem atendimento humano há mais de N dias → descartar;
2. tinha nome antes → restaurar o nome;
3. nunca teve nome → descartar se a situação estiver na lista; senão, não mexer.

"Atendimento humano" ignora eventos do usuário `Sistema`, de integrações e alterações de campo.

### Importar planilha sem roleta

```bash
python -m scripts.importar_leads.checar_duplicados <planilha.xlsx>
python -m scripts.importar_leads.importar plano
python -m scripts.importar_leads.importar aplicar --executar --grupo novo --limite 1
python -m scripts.importar_leads.importar aplicar --executar
```

Quem não existe no CV é cadastrado. Quem existe e está em situação reativável é reativado. Quem
já está em atendimento não é tocado.

## Pegadinhas da API do CV (aprendidas na prática)

- **Alterar nome exige o header `origemcv: true`.** Sem ele, a API responde `sucesso: true` e
  ignora o nome silenciosamente.
- **Editar exige `email` ou `telefone` no corpo**, mesmo com `idlead`. Sem eles, a resposta é
  `400 email_telefone_vazio`.
- **Reativar um lead sem mandar `nome` grava "Sem nome"** por cima do nome existente. Sempre
  releia o lead e reenvie o nome atual.
- **`pausar_hook: true`** evita disparar webhooks. Isso é essencial quando a correção desfaz algo
  que uma integração fez, senão a integração recebe a alteração de volta.
- **Travas úteis numa edição cirúrgica:** `converter: false`, `reativar_lead: false`,
  `permitir_trocar_atendente: false`, `ignorar_email: true`. E reenvie o `idsituacao` atual, porque
  editar um lead cancelado sem ele pode reativá-lo.
- **Para não cair na roleta:** `lead_utilizar_fila`, `utilizar_fila_gestor` e
  `utilizar_fila_corretor` como `false`, `idimobiliaria` fixa e `remover_corretor: true` na
  reativação.
- **Descartar exige motivo de cancelamento**, e cada motivo só vale para certas situações (veja
  `GET /v1/comercial/motivos-cancelamento-lead`). O nome precisa bater exatamente, porque um nome
  novo **cria um motivo novo** na base. A restrição de situação existe só na tela; a API aceita.
- **O mesmo vale para `midia`:** um slug inexistente cria mídia nova. Prefira `idmidia`.
- **A busca por telefone (`GET /v1/comercial/leads?telefone=`) é parcial.** Um telefone curto ou
  inválido casa com dezenas de leads alheios. Confirme cada resultado comparando DDD + últimos 8
  dígitos, ou o e-mail exato.
- **O histórico de alteração de campos não está na API.** `/cvdw/leads/historico/situacoes` é
  uma view filtrada que só traz mudanças de situação, e pula os IDs de "Modificou o campo". O dado
  existe apenas na aba Histórico do painel (`/gestor/comercial/leads/<id>/historico`).
- **No CVDW, `nome` é o nome atual do lead**, não um retrato histórico. As conversões antigas
  também mostram o nome de hoje.
- **O CVDW `/leads` leva ~9 s por página e limita a 500 registros.** Numa base grande, pagine em
  paralelo (`listar_sem_nome.py` usa 6 conexões).
- **A sessão do painel expira em algumas horas** e devolve a tela de login com HTTP 200. Detecte
  pelo conteúdo (`sessao_caiu()`), não pelo status.

## Segurança e LGPD

Este repositório contém **apenas código**. O `.gitignore` bloqueia credenciais (`config.json`,
`curl.txt`, `cookie.txt`) e qualquer dado de cliente (`dados/`, `*.csv`, `*.xlsx`, `*.json`,
`*.html`). Não remova essas regras. Os CSVs gerados têm nome, e-mail e telefone de pessoas reais.
