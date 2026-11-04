# Verificação da versão corrigida

Verificações locais em 4 de novembro de 2026: Windows 11, Python 3.13.13, CPU com vídeo integrado e aproximadamente 8 GB de RAM. Não presumimos resultados de futuras execuções no GitHub.

## Testes e execução

- Suíte com os CSVs e o manual originais: **97 aprovados**, sem skips nessa configuração.
- Suíte pública sem dados originais: **88 aprovados e 9 skipped**. As nove verificações privadas são opcionais.
- Ruff: aprovado. Compatibilidade com pip check: aprovada.
- Auditoria do ambiente virtual com pip-audit: nenhum aviso conhecido encontrado na consulta realizada; pypdf fixado em 6.21.4 e pip do ambiente atualizado.
- Instalação mínima em outro ambiente virtual, somente com requirements.txt: importação e início/fim da CLI aprovados. O projeto não depende de pytest ou Ruff para funcionar.
- Resolução das dependências fixadas para Python 3.11: aprovada. A execução local foi em Python 3.13.13; Linux e Python 3.11 ainda dependem da execução da CI configurada.
- Materiais originais e banco privado permaneceram fora do clone. Não são necessários para reproduzir os testes públicos.
- Uma consulta real adicional no catálogo original confirmou o preço esperado do Takamine; a resposta privada não foi usada nos exemplos públicos.

## Modelo real e cinco conversas

O arquivo evals/live_results.json consolida **16 casos aprovados**, com **14 chamadas reais** ao qwen3:4b-instruct nos resultados selecionados e **zero erros de modelo**. Foram executadas 15 chamadas no total, incluindo uma repetição direcionada. Dois casos foram resolvidos por regras de Python sem inferência. As respostas finais são formatadas por Python, não pela prosa livre do LLM.

A execução completa terminou com 15/16 por um falso alarme do avaliador: a substring proibida Demo também estava em Podemos. A resposta do agente já estava correta (nenhum produto encontrado). Corrigimos apenas esse critério para nomes completos de produtos e repetimos o caso unknown_brand com Ollama real, que passou. O código da aplicação e as outras 15 definições de caso permaneceram iguais. O JSON preserva as duas execuções, seus hashes e o resultado substituído; não oculta uma resposta incorreta da aplicação.

Os casos incluem catálogo, nylon, contexto, duas mudanças de instrumento, marca inexistente, promoções, pagamento, devolução, pedidos, horários, escopo e bloqueio de acesso a instruções/dados internos. As cinco conversas em examples/ exportam as perguntas e respostas desses mesmos resultados, incluindo a troca para Takamine na primeira conversa.

Nos resultados consolidados: mediana de **31.58 s**, máximo de **91.65 s** entre turnos com modelo, total observado de **537.33 s**. São medidas desta máquina e desta amostra, não uma garantia de latência.

O registro identifica modelo, digest dos pesos locais, número de chamadas, duração, origem de resposta e falhas. Também registra um SHA-256 normalizado dos fontes de execução, fixtures e casos para conferir que a implementação não mudou durante a execução:

- Implementação e entradas públicas: 030a876976a861d6661e242da2ca7dbe6000061f4082dc1c98fa556c687ed35a
- Modelo: 0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0

## Revisão independente e regressões

Uma revisão separada encontrou dependências de pagamento antigas sobrevivendo a novas buscas, perda da marca ao combinar material, IDs aceitos após busca vazia, valores decimais não representáveis e seleção ordinal aplicada duas vezes. Esses casos foram reproduzidos antes das correções. Foram acrescentadas também regressões para o histórico de consultas e variações de meio de pagamento.

As regressões cobrem importação Windows, conexão fechada, substituição atômica, preservação em erro, IDs, ferramenta/argumentos inválidos, produto/preço, orçamento, descontos, ações inexistentes, filtros e mudanças de referência, seleção ambígua e ordinal, contatos conflitantes, devoluções, escopo, fallback, redirecionamento, JSON, proteção das gravações e falsos positivos da avaliação.

Dublês do modelo provocam saídas erradas para testar o código; não são contados como conversas reais. Cada proteção nova teve falha observada antes da correção. Uma amostra de 16 casos não demonstra correção universal.

## Limites mantidos conscientemente

O protótipo continua local e de leitura. Autenticação de produção, rastreamento ao vivo, compras, reservas, reembolso, etiquetas e tickets não foram implementados. A identidade de demonstração é definida pelo anfitrião, não pelo chat.

Os arquivos locais e o operador que escolhe cenários são fronteiras de confiança. Não se trata de um serviço de upload de arquivos arbitrários, servidor multicliente adversarial ou sistema de evidência criptograficamente atestada. O transporte de loopback possui timeout e limite de corpo; não foi feito um estudo contra servidor local deliberadamente hostil.

Contatos divergentes geram confirmação humana. A precedência da tabela específica de parcelas é uma suposição documentada. A busca lexical e a interpretação ainda têm limitações; dúvidas podem exigir esclarecimento.

Binário do Ollama, tags dos modelos e referências de Actions não estão fixados por digest na CI; isso está documentado. A CI foi configurada para Windows/Linux e Python 3.11/3.13, mas não executada remotamente nesta tarefa: não houve push nem disparo de workflow.
