# Real agent conversations — local Ollama

Model: `qwen3:4b-instruct`. Captured during real local inference; individual answers may be model text or Python safety guards.
Data: publicly shareable fictional fixtures, not the private recruitment data.

## Conversation 2: Promotion, PIX and instalments

*Purpose: Catalog, active promotion and non-stacking payment rules*

**Customer:** Vi uma guitarra no catálogo por volta de R$ 2.100. Ela está com algum desconto?

**Agent:** Sim, a guitarra está com desconto! A **Guitarra Demo Promocional** está com **20% de desconto**. O preço original é R$ 2.100,00, e com o desconto, o valor cai para **R$ 1.680,00**. O desconto não se acumula com outras ofertas, como o PIX. O produto está disponível em estoque (2 unidades).

**Tools:** search_products, get_applicable_promotions

**Response source:** model

**Customer:** Se eu fechar no PIX, dá mais 5% por cima? E quanto ficaria em seis parcelas?

**Agent:** Não, o PIX **não inclui** mais 5% de desconto. O valor final com desconto (R$ 1.680,00) é o mesmo que o preço promocional.  

Para **seis parcelas**, cada parcela fica em **R$ 280,00** (total: R$ 1.680,00). As parcelas são iguais e sem juros.

**Tools:** calculate_payment_options

**Response source:** model
