# Empório da Música - agente de atendimento

Protótipo em Python para o desafio de AI Engineer da Artefact. Consulta catálogo, pedidos e políticas por uma CLI em português, com Ollama local. É um sistema de leitura: não compra, não reserva, não emite etiquetas e não decide aprovações de devolução.

## A ideia em três passos

1. **Interpretar:** Python antecipa consultas evidentes e o LLM seleciona ferramentas para a mensagem e seu contexto. Há no máximo uma chamada de planejamento ao modelo por turno, com até seis ferramentas.
2. **Consultar:** funções Python permitidas leem SQLite, verificam o titular do pedido e calculam valores com `Decimal`.
3. **Responder:** Python formata os resultados reais. **O texto livre do LLM não é mostrado ao cliente.** Isso impede que um preço inventado, uma porcentagem ou uma ação alegada pelo modelo substituam os fatos consultados.

Não é uma garantia universal de correção: o modelo e as regras de interpretação ainda podem entender uma intenção incorretamente. Por isso há filtros explícitos, pedidos de esclarecimento e avaliações de produto, argumentos e resposta. As evidências identificam chamadas do modelo, falhas e a origem de cada resposta.

## Rodar no Windows

Requisitos: Python 3.11 ou posterior e [Ollama](https://ollama.com/download). Mantenha o Ollama aberto. O modelo `qwen3:4b-instruct` ocupa aproximadamente 2,5 GB em disco; é gratuito e funciona em CPU, mas pode demorar em máquinas com pouca memória. O download é necessário uma vez. Depois, as mensagens ficam no computador.

Execute na pasta do projeto:

```powershell
ollama pull qwen3:4b-instruct
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/prepare_data.py --source-dir fixtures --policy-json fixtures/demo_policies.json --db data/demo.db
.\.venv\Scripts\python.exe scripts/check_local.py
.\.venv\Scripts\python.exe main.py --db data/demo.db
```

Pergunte: `Quero um violão de nylon até R$ 900.` Depois: `E a Guitarra Demo Promocional no PIX e em seis parcelas?` Digite `sair` para encerrar. Por padrão, não há cliente autenticado e consultas de pedidos são recusadas. **Somente com dados fictícios**, `--demo-customer-id 1` simula a identidade definida pelo anfitrião; não é autenticação real.

### Linux e macOS

Os mesmos comandos funcionam substituindo `py -3` por `python3` e `.\.venv\Scripts\python.exe` por `.venv/bin/python`. Se o Ollama não responder, abra seu aplicativo ou execute `ollama serve` em outro terminal. `scripts/check_local.py` verifica serviço e modelo sem fazer inferência.

O projeto não carrega `.env` automaticamente. As variáveis opcionais são `OLLAMA_MODEL` e `OLLAMA_BASE_URL`; esta última aceita apenas HTTP de loopback com `/v1`. O transporte ignora proxies e recusa redirecionamentos. Cada chamada ao modelo tem limite de 120 segundos; o agente pode devolver fatos já consultados se o modelo falhar, mas uma avaliação real não conta esse fallback como sucesso do LLM.

## Usar os materiais originais sem publicá-los

O catálogo e os clientes de `fixtures/` são **fictícios**. As políticas de demonstração também são fictícias e não substituem o manual fornecido no desafio. Não redistribuímos os clientes, o ZIP ou o PDF interno.

Com o ZIP original:

```powershell
.\.venv\Scripts\python.exe scripts/import_challenge_zip.py "C:\materiais\desafio.zip" --db data/emporio.db
.\.venv\Scripts\python.exe main.py --db data/emporio.db
```

Ou com os seis CSVs em uma pasta dedicada e o manual separado:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_data.py --source-dir "C:\materiais\csvs" --manual "C:\materiais\politicas_da_loja.pdf" --db data/emporio.db
```

A pasta deve conter exatamente uma cópia de cada tabela: `categories`, `products`, `customers`, `orders`, `order_items` e `promotions`, com os cabeçalhos do desafio. O importador aceita `products.csv` e nomes terminados em ` - products.csv`. Não aponte para todo o diretório temporário do Windows, que pode conter cópias duplicadas.

A importação valida colunas, valores e relacionamentos, fecha as conexões e só substitui o banco ao terminar com sucesso. Temporários têm nomes únicos e são ignorados pelo Git. **Os scripts de avaliações e gravações públicas recusam qualquer banco que difira das fixtures e políticas fictícias**, inclusive alterações nos clientes.

## Verificar

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip_audit
.\.venv\Scripts\python.exe scripts/run_evals.py --db data/demo.db --output evals/live_results.json
.\.venv\Scripts\python.exe scripts/capture_examples.py --db data/demo.db --from-evals evals/live_results.json --out-dir examples
```

`requirements.txt` contém só a dependência de execução. `requirements-dev.txt` declara as ferramentas de desenvolvimento; `requirements-dev.lock` fixa também suas dependências transitivas. Atualizações exigem testes e nova auditoria, não apenas editar um número de versão.

`pytest` é determinístico: usa ferramentas reais e respostas controladas onde não precisamos testar o LLM. O teste HTTP usa um servidor de loopback e não é apresentado como inferência real. Para incluir os seis testes opcionais do desafio original, defina `ARTEFACT_SOURCE_DIR` e `ARTEFACT_POLICY_PDF` no terminal; os arquivos continuam locais.

`run_evals.py` faz inferência real, mantém o contexto entre casos da mesma sessão e verifica ferramenta, argumentos relevantes, produtos, valores exibidos, políticas e alegações proibidas. Falha do modelo não vira aprovação. Os casos de autorização e bloqueio de dados internos podem usar zero chamadas ao LLM, explicitamente registrados.

`capture_examples.py --from-evals` exporta **os mesmos turnos** já avaliados, conferindo pergunta, modelo, sucesso e identidade de demonstração. Assim não confunde uma conversa com outra inferência. Sem essa opção, ele executa novas conversas reais. Nunca fabrica uma resposta para substituir uma falha.

## Demonstrações e aderência ao desafio

Há cinco conversas em `examples/live_conversation_1.md` a `live_conversation_5.md`: orçamento e mudança de produto; promoção e PIX; devolução; pedido e privacidade; horários e assunto fora do escopo. Os resultados completos ficam em `evals/live_results.json`; [o registro de verificação](docs/verification.md) informa ambiente, resultados e limites. São amostras, não uma taxa geral de precisão.

| Pedido do desafio | Como demonstramos |
|---|---|
| Python e agente de texto com persona | CLI, prompt em português e respostas da Empório da Música |
| Contexto e escolha entre dados e políticas | Ferramentas separadas, filtros persistidos, resolução do produto e páginas do manual |
| Perguntas fora do escopo | Caso real de futebol e recusa restrita ao atendimento da loja |
| Três a cinco conversas e caso não trivial | Cinco conversas; descontos não cumulativos, parcelas, política e privacidade |
| README e transparência de decisões/IA | Este documento e o histórico incremental de correções |

A CI determinística cobre Windows e Linux, Python 3.11 e 3.13. A CI de Ollama executa cinco cenários e distribui todos os casos de avaliação em runners Linux temporários. A instalação do Ollama no runner vem do script oficial; seu binário e as tags de modelo/Actions não estão fixados por digest, portanto a reprodução não é byte a byte. Nenhuma execução futura da CI é presumida bem-sucedida: veja o resultado do run.

## Decisões e suposições

- **Sem framework de agentes:** funções pequenas e biblioteca padrão bastam para as seis ferramentas; isso deixa autorização, cálculos e fluxo visíveis. O único pacote de execução é `pypdf`, para importar o manual.
- **Ollama/Qwen3 4B Instruct:** evita contas, chaves e cobrança por API. O compromisso é a latência e memória locais. A configuração usa temperatura zero, geração limitada e uma chamada de planejamento por turno; nenhuma cadeia de raciocínio é publicada.
- **Prompt:** define persona informal e profissional, escopo, ferramenta para cada tipo de dúvida e distinção entre dados e instruções. O prompt ajuda a interpretar; não é a barreira de segurança. Identidade, consultas, preços e resposta final ficam em Python.
- **SQLite:** snapshot local com relacionamentos validados e consultas de leitura parametrizadas. O modelo nunca recebe uma ferramenta para executar SQL ou ler a tabela de clientes.
- **Busca lexical de políticas:** páginas e termos normalizados funcionam para um manual curto e são fáceis de inspecionar. A resposta apresenta trechos curtos relevantes com página; evita uma paráfrase inventada e não exibe o manual inteiro. Uma busca pode perder uma formulação incomum.
- **Conflitos do manual:** se há telefones divergentes, o agente pede confirmação do canal oficial. Nos cálculos de parcelas, adotamos a tabela específica: 1-3x com mínimo de R$ 50, 4-6x R$ 80 e 7-12x R$ 100, em vez do mínimo geral de R$ 100. A resposta identifica essa escolha e orienta confirmação humana.
- **Devolução:** o agente mostra o que o material diz e encaminha a avaliação de embalagem e sinais de uso ao atendimento humano. Não aprova nem nega automaticamente, não emite etiqueta e não interpreta o manual como parecer jurídico.
- **Contexto:** até oito turnos por sessão, com redução do histórico enviado ao modelo; não persiste depois de sair. Mantém orçamento/material ao refinar a mesma categoria, mas uma referência explícita a outro produto inicia nova seleção. Vários produtos possíveis exigem identificação antes do cálculo.
- **Promoções e pedidos:** registros históricos, sem validade de campanha ou posição atual da transportadora inferida. Promoções não se acumulam entre si nem com PIX.

## Limitações e próximos passos

Não há autenticação de produção, integração com transportadora, estoque ao vivo, pagamentos, tickets ou registro de reclamações. A possibilidade descrita no manual de registrar e encaminhar reclamações é uma limitação documentada deste protótipo; ele pode orientar o contato humano e não afirmar que registrou.

As proteções não tornam a interpretação de linguagem infalível. Há vocabulário e regras explícitas no prefetch, uma seleção limitada de ferramentas e busca lexical; pedidos ambíguos podem precisar de esclarecimento. Nomes e textos do catálogo/manual continuam sendo dados locais que devem vir de fonte confiável. Em uma evolução, ampliaria casos avaliados, testes de atualização de políticas, autenticação real e integrações de atendimento, antes de acrescentar uma interface web.

## Uso de IA no desenvolvimento

Usei ChatGPT/Codex para auditoria do enunciado e código, elaboração de regressões, investigação de falhas do SQLite no Windows, mudanças de implementação e documentação. A auditoria encontrou preços que não correspondiam ao produto, mistura de contexto, avaliações permissivas e demonstrações parcialmente adequadas. As correções foram acompanhadas de testes que primeiro reproduziram as falhas, depois passaram.

As decisões continuam explícitas no código e neste README. Testes com cliente falso não são prova do comportamento do modelo; demonstrações reais informam modelo, número de chamadas, duração, origem da resposta e falhas. Não publico os materiais privados do processo.
