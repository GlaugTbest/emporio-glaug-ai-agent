# Verificação da versão corrigida

Verificações locais em 4 de novembro de 2026, Windows 11, Python 3.13.13, CPU com vídeo integrado e aproximadamente 8 GB de RAM. Não presumimos resultados de futuras execuções no GitHub.

## Evidência automatizada

- Suíte determinística com os CSVs e o manual originais: 81 testes aprovados, sem skips nessa configuração.
- Sem os materiais originais, nove verificações privadas são opcionais e devem aparecer como skipped.
- Ruff: aprovado. `pip check`: aprovado.
- `pip-audit` do ambiente virtual: nenhum aviso conhecido encontrado na consulta. A ferramenta foi instalada e o pip do ambiente virtual atualizado; o pypdf foi fixado em 6.21.4.
- Os materiais originais e o banco gerado a partir deles ficaram fora do repositório; não são necessários para os testes públicos.
- Uma consulta adicional real ao catálogo original confirmou o preço esperado do Takamine. Sua resposta não é publicada como demonstração pública.

## Modelo real e respostas verificadas

`evals/live_results.json` registra 14 casos, todos aprovados na execução registrada: catálogo, preferência por nylon, contexto, troca de instrumento, promoção, pagamento, devolução, pedido próprio, pedido de terceiro, horários, fora do escopo, bloqueio de instruções/dados e consulta nominal.

Foram 12 chamadas reais ao `qwen3:4b-instruct`, sem erro de modelo nessa execução. Dois casos foram resolvidos por regras de Python sem chamar o modelo. As respostas finais são formatadas por Python; não são a prosa livre do LLM. Cada resultado identifica essa origem, o número de chamadas e o tempo observado.

As cinco conversas em `examples/` exportam as perguntas e respostas desses mesmos resultados. O exportador recusa perguntas diferentes, falhas, outro modelo ou identidade de demonstração incompatível. Os scripts públicos comparam todas as tabelas e as políticas com as fixtures e recusam dados privados.

A primeira execução completa observou mediana de 36,50 segundos e máximo de 84,46 segundos entre os turnos com modelo, totalizando 433,47 segundos de inferência/consulta. Isso caracteriza esta máquina e essa amostra, não uma garantia de latência. Os tempos por caso do JSON são a referência da execução publicada.

## Regressões cobertas

Importação no Windows e fechamento de conexão; substituição atômica do banco; preservação do banco anterior em erro; IDs fora da faixa do SQLite; ferramentas e argumentos inválidos; preço atribuído ao produto errado; orçamento confundido com preço; porcentagem inventada; alegação de reserva/cobrança; mudança de instrumento; pagamento ambíguo; seleção ordinal; orçamento/material persistidos; filtro de nylon no follow-up; contatos conflitantes; devolução sem decisão automática; escopo; fallback explícito do modelo; redirecionamento HTTP; JSON inválido; dados privados em gravações; falso positivo do avaliador.

Esses testes verificam regras e resultados observáveis. Dublês do modelo provocam respostas erradas de propósito para verificar se o código as rejeita; esses testes não são contados como demonstração de um LLM real.

## Reproduzir

Use os comandos do README. O banco público deve ser criado a partir de `fixtures/`. A suíte determinística não depende de Ollama nem de dados privados. A avaliação real exige o modelo instalado.

A CI foi configurada para Windows/Linux e Python 3.11/3.13, mas não foi executada remotamente nesta revisão: não houve push nem disparo de workflow.

Os 14 casos e os testes não demonstram correção universal. Interpretação de linguagem, busca lexical, atualizações dos dados e condições não cobertas podem exigir novas regressões e esclarecimento ao cliente.
