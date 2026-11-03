# Empório da Música — customer service agent

A small Python agent built for the Artefact AI Engineer challenge. It answers customer messages in Portuguese using a product catalog, order records and a store policy document. It can explain an answer, but it cannot place an order or promise that a return has been approved.

The app runs on a computer with Ollama. There is no account, paid LLM API, or hosted service.

## Run it

You need Python 3.11 or newer and [Ollama](https://ollama.com/download). The recommended model is `qwen3:4b-instruct` (about 2.5 GB). It is a free download; unlike the thinking-oriented `qwen3:4b` tag, it is intended to give direct responses without exposing intermediate reasoning.

On Windows PowerShell, from a clone of this repository:

```powershell
ollama pull qwen3:4b-instruct
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/prepare_data.py --source-dir fixtures --policy-json fixtures/demo_policies.json --db data/demo.db
.\.venv\Scripts\python.exe scripts/check_local.py --model qwen3:4b-instruct
.\.venv\Scripts\python.exe main.py --db data/demo.db
```

Keep the Ollama desktop app running. If necessary, start `ollama serve` in a different terminal. After the model is downloaded, inference runs on your computer without sending customer messages to a cloud LLM. CPU-only inference is supported but can be slow.

Try asking: *"Estou começando a tocar violão e tenho até R$ 900. O que você tem disponível?"* Then ask a follow-up without repeating the budget. Type `sair` to quit.

### Run it with the assignment's original data

The recruitment materials contain an internal policy manual and customer data, so they are **not redistributed** in this public repository. The original ZIP can be imported locally without copying its contents into Git:

```powershell
.\.venv\Scripts\python.exe scripts/import_challenge_zip.py "C:\path\to\Desafio_Tecnico_AI_Engineer.zip" --db data/emporio.db
.\.venv\Scripts\python.exe main.py --db data/emporio.db
```

The import script locates the six CSVs and the PDF, reads their content into a local SQLite database, and removes its temporary extracted copy. `data/*.db` is ignored by Git. The `fixtures/` folder contains deliberately fictional sample records; they are not the real customers.

## Why this design

I kept the application close to the assignment. A CLI is enough to demonstrate the agent, and Python's standard library plus `pypdf` cover the data and model integration.

- **Local LLM:** Qwen3 4B Instruct runs through Ollama's native `/api/chat` endpoint, with short responses and thinking disabled. No API keys or paid provider SDKs.
- **Tools and business rules:** The model can request product, promotion, policy or order data. Python owns the queries, discount calculations and authorization checks; the model never writes SQL. Because small models sometimes skip tool calls, straightforward intents also have a short deterministic prefetch step before generation. The prefetch is deliberate routing, not an LLM-selected tool call.
- **Data:** The six CSVs are loaded into SQLite with schema and relationship checks. Catalog results only label a product available when it is active **and** has positive stock. Order records and promotions are historical snapshots, not live integrations.
- **Policy retrieval:** The provided PDF is split into searchable pages with normalized terms. This is easier to explain and maintain than embeddings for a short manual, although unusual paraphrases can still be missed.
- **Conversation context:** The latest eight turns are kept in memory for follow-up questions. The user session is not persisted after exiting.

Orders can only be read for a customer ID supplied by a trusted host. The CLI option `--demo-customer-id 1` simulates such a host **for local testing only**; it is not authentication and must not be used on a publicly reachable service. An ID or authorization asserted by the customer in chat never changes the session's identity.

The manual has conflicting contact details and overlapping parcel minimums. The agent should acknowledge ambiguity instead of inventing a definitive answer. Promotions are not cumulative with each other or with PIX discounts, and the promotion CSV has no expiry dates to infer.

## Tests and demonstration

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/capture_examples.py --db data/demo.db
.\.venv\Scripts\python.exe scripts/run_evals.py --db data/demo.db
```

`pytest` covers imports, stock, SQL/tool validation, discounts, policy retrieval, conversation memory, incorrect model-generated amounts and access control. The repository includes synthetic fixtures so the standard suite is reproducible; additional checks using the original materials are optional and local-only (`ARTEFACT_SOURCE_DIR` and `ARTEFACT_POLICY_PDF`).

The four scenarios in `evals/scenarios.json` cover a beginner's budget, a promotion with PIX/instalments, a return with missing packaging, and an order request involving another customer's data.

**Verified demonstration:** The [real Qwen3 GitHub Actions run](https://github.com/GlaugTbest/emporio-glaug-ai-agent/actions/runs/41721596429) completed all four two-turn conversations using only public fictional fixtures. The recorded outputs are in [`examples/live_conversation_1.md`](examples/live_conversation_1.md), [`2.md`](examples/live_conversation_2.md), [`3.md`](examples/live_conversation_3.md), and [`4.md`](examples/live_conversation_4.md). Matching evaluation evidence is in `evals/live_result_1.json` through `live_result_4.json` (one representative case per scenario, all four passed). Each transcript identifies its tools and whether the reply came directly from the model or a deterministic Python safety rule. A passed scripted evaluation does not guarantee that all possible conversation variations are accurate.

The public deterministic suite passed **37 tests**, with **6 private-data-only checks skipped**. Supplying the original ZIP locally lets those checks run too (**43 passed** with the original challenge files). The sensitive inputs are not required for the public demonstration.
 `capture_examples.py` saves **actual model output**, including which tools were used, to Markdown. It does not fabricate a conversation when a run fails. You can reproduce a single case with `--scenario 3 --out examples/my_test.md`.

`run_evals.py` separately checks expected tools, factual markers and forbidden claims. These checks are useful but not a substitute for manually reviewing the transcript. A scripted HTTP test verifies that the code can communicate with Ollama; it is explicitly not counted as a real-model evaluation.

The GitHub Actions workflows run the deterministic tests and, separately, attempt real-model conversations with only fictional fixtures on temporary Linux runners. The CI artifacts contain model outputs when a scenario completes; inspect the run result before relying on them as evidence.

## What it does not do

This is a read-only prototype. It cannot make purchases, reserve stock, issue refunds, open support tickets, authenticate customers or track deliveries in real time. Production would require a real authentication provider, integrations to current store systems, more policy-retrieval tests and a larger evaluated conversation set. A web interface could be added, but it is not required by the assignment and would add deployment and maintenance work without improving the current agent.

## AI-assisted development

I used ChatGPT for code drafting, reviewing the supplied documents, writing test cases and investigating the Ollama integration. Tests exposed several issues in the initial version, including model responses without tool calls and unsupported prices; those led to the deterministic guardrails above. The code and test outputs were checked against the supplied materials. In particular, mocked tests are not presented as proof that a real language model answered correctly.
