# Empório da Música - AI Customer Service Agent

A focused **Python + LLM tool-calling prototype** for Artefact's AI Engineer technical challenge. It answers in Brazilian Portuguese about instrument availability, prices, promotions, payment conditions, store policies, and (only in a trusted customer context) order status. It does not create purchases or refunds.

> **Current verification status:** the SQLite importer and deterministic tools have been exercised against the original challenge files locally; pytest integration tests use scripted model responses. **No live LLM API result is claimed** until `scripts/capture_examples.py` and `scripts/run_evals.py` are run with a real `OPENAI_API_KEY`.

## Quick start (synthetic data)

Python 3.11+ is recommended. Shell commands assume the repository root as the working directory.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/prepare_data.py --source-dir fixtures --policy-json fixtures/demo_policies.json --db data/demo.db
# bash/zsh:
export OPENAI_API_KEY="your-provider-api-key"
# Windows PowerShell: $env:OPENAI_API_KEY="your-provider-api-key"
python main.py --db data/demo.db
```

The sample catalog, policy sections, customers and orders under `fixtures/` are **entirely fictional** and must not be represented as real customer/store data. `OPENAI_MODEL` defaults to `gpt-4.1-mini`; you can override it using `--model`. The chosen OpenAI model must support Chat Completions function calling. `.env.example` documents configuration; an actual `.env` file is not loaded automatically (export variables in your shell).

## Using the supplied challenge files locally

The original challenge ZIP contains six CSVs, a 2025 internal policy PDF and an assignment PDF. Unzip it **outside this repository** (or under a gitignored `inputs/` directory). For example:

```bash
python scripts/prepare_data.py \
  --source-dir "../extracted-challenge" \
  --manual "../extracted-challenge/data/políticas_da_loja.pdf" \
  --db data/emporio.db
python main.py --db data/emporio.db
```

Paths depend on where you unzip: `--source-dir` searches recursively for six CSVs with the original `desafio_tecnico_ai_eng - <table>.csv` naming convention, or `fixtures/<table>.csv`; `--manual` must point to the actual policy PDF. CSV files require all expected columns; wrong schemas or foreign keys fail import without overwriting the previous DB. The importer preserves categorical relationships, `Decimal`-friendly numeric strings and raw specifications. SQLite `PRAGMA foreign_keys` validates integrity. Original source files and `.db` outputs are **never** added to Git.

## Run the agent

```bash
python main.py --db data/emporio.db
# LOCAL DEMONSTRATION ONLY - NOT AUTHENTICATION:
python main.py --db data/demo.db --demo-customer-id 1
```

The normal CLI denies access to order data. `--demo-customer-id` simulates an identity already established by a trusted external application; anyone with terminal access can select a value, so **do not expose this CLI mode to real customers or deploy it with personal data**. A production application would authenticate users server-side and inject the authenticated customer ID without asking the LLM to choose it.

## Architecture

```text
Customer message -> OpenAI LLM + session history
    -> native function call with JSON arguments
    -> allowlisted Python StoreTools
       -> read-only SQLite (catalog, promotions, scoped orders)
       -> lexical retrieval over extracted policy PDF pages
    -> structured tool result -> LLM -> Portuguese answer
```

- **OpenAI SDK / Chat Completions:** direct SDK keeps the call path inspectable for an interview. `gpt-4.1-mini` is a configurable starting point, not a benchmark claim. A live key and access to that model are required.
- **SQLite:** the challenge provides a small static CSV dataset. Explicit SQL prepared statements and a read-only connection keep the model away from arbitrary SQL and writes. Product availability requires both `status == active` and `stock_quantity > 0`.
- **Tools:** `search_products`, `get_product_details`, `search_store_policies`, `get_applicable_promotions`, `calculate_payment_options`, and `get_order_status`. Explicit schemas, argument validation, error objects, short search results and bounded tool rounds avoid unnecessary orchestration. The LLM cannot add an `authenticated_customer_id` tool argument.
- **Policy retrieval:** one short policy manual does not justify embeddings, a vector store or a LangGraph flow. The PDF is extracted locally using `pypdf` into page-labeled chunks. Token overlap (with Portuguese accent normalization and a small synonym list) ranks the top two pages and returns their origins. This favors simple explainability over semantic recall; paraphrases not in the synonym list may fail.
- **Conversation context:** in-memory per-session turn bundles, capped to eight turns, retain tool results together with messages. Restarts lose history and there is no account/session isolation beyond the host-provided session ID. CLI is single-session.
- **Prompt policy:** tool use is required for operational facts; model text, CSV fields and policy data are treated as untrusted. The assistant must admit unavailable information, avoid unsupported claims and decline out-of-domain tasks. A narrow guard blocks ungrounded currency/percentage responses when the model used no tools; it is not a complete post-generation factual validator.

### Business rules and assumptions

1. **Prices, stock and status:** product listings come from a snapshot; an `active` product with zero stock is unavailable. Neither promotions nor orders are real-time.
2. **Discounts:** promotional entries have `is_active` but no start/end dates. Only active entries apply, only to purchasable products. We do not assume expiry from campaign names. A product may receive at most one promotion. The separate 5% PIX discount applies to non-promotional prices only. The payment tool uses `Decimal` and reconciles installment rounding in the last installment.
3. **Credit installments:** the policy PDF contains a general R$100 minimum, conflicting with section 3.1's specific thresholds (1-3x: R$50, 4-6x: R$80, 7-12x: R$100). The **specific** section 3.1 schedule is used. Unresolved disputes require human review. For other payment combinations, use the policy manual instead of pretending the payment tool accepts split tender.
4. **Contacts:** the cover and section 1.2 differ in email accent, and section 7 lists a different WhatsApp number from the general number. The agent is instructed not to invent a definitive contact when sources conflict. Confirm any handoff channel against official store details; the store is fictitious.
5. **Privacy:** order queries enforce `(order_id, authenticated_customer_id)` in SQL and return no customer email, address or name. Possession of an order number or an asserted identity in chat does not authenticate anyone. The original input contains personal-looking data and a manual labeled internal; not redistributing them avoids inadvertent exposure.
6. **Refunds, complaints and tracking:** there are no mutation or carrier APIs. The agent can explain a policy but cannot approve a refund, register a complaint, contact a manager or promise live tracking.

## Tests and evidence

```bash
python -m pytest -q
python scripts/capture_offline_checks.py
# Requires a working API key and costs whatever the provider charges:
python scripts/capture_examples.py --db data/demo.db
python scripts/run_evals.py --db data/demo.db --output evals/live_results.json
```

- **Deterministic tests (`tests/`):** data import/relationships/atomicity; availability rules; search filters; invalid inputs, SQL injection attempts, ineligible promotions, PIX non-stacking, installment rounding, policy retrieval, order privacy; mocked-LLM multi-turn tool flow, out-of-scope and bounded failure. These tests really invoke the SQLite-backed tools but **do not** invoke a remote LLM.
- **Offline evidence (`examples/offline_tool_checks.md`):** four distinct multistep tool traces generated from the synthetic SQLite dataset. They are clearly labeled **NOT LLM transcripts**.
- **Live examples (`scripts/capture_examples.py`):** writes four conversations to `examples/live_conversations.md` from actual API responses. It does not ship invented conversations. Review resulting answers for accuracy before submission.
- **Live LLM evals (`evals/cases.json`, `scripts/run_evals.py`):** check selected tools, expected phrases and disallowed claims; save an actual timestamped `evals/live_results.json` only after execution. `pytest` pass counts cannot substitute for this run. A nonzero exit code indicates failed live scenarios.

## Known limitations / what I'd do next

The prototype has no real login, no persistent conversation store, no real-time inventory/order/track-and-trace feed, no interface besides CLI, no asynchronous complaint/refund action and no web endpoint. Retrieval is keyword-based and can miss paraphrases; structured facts from policy text still depend on model interpretation. A larger deployment would add proper authentication, server-side session management, richer policy section indexing, schema-aware answer validation, provider error monitoring and an API/frontend only after quality evaluation. The fixture's invented facts are strictly for development. The tool's sale/price calculations have not been verified against a live payment platform.

## AI-assisted development

ChatGPT (GPT-6) was used to analyze the task and policy material, propose the architecture, write and review initial code, and help design deterministic tests and evaluation scripts. The candidate should independently review generated code, run the live scenarios, interpret failures, and be prepared to explain technical tradeoffs. AI assistance is documented rather than hidden. There is no claim that an AI assistant independently established production readiness.

## Submission

The assignment requests a **public GitHub repository with real development commits**, this README and 3-5 example conversations, with at least one nontrivial. The technical assignment specifically requests **replying to the recruiter by email with the repository URL**. If an application form separately requests a PDF response, include the concise English PDF summary, but the challenge PDF itself does not require a PDF deliverable. Do not change the submitted repository after the actual deadline. Before submitting, run at least one **live LLM** flow and commit 3-5 genuinely captured conversations in place of offline-only evidence.