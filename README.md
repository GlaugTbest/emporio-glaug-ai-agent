# Empório da Música — Customer Service Agent

A small Python agent for Artefact's AI Engineer challenge. It answers customer questions in Brazilian Portuguese, looks up the store's catalog and policies, and explains when it cannot complete a request.

**Runs locally and costs nothing to use.** The language model runs on your computer with [Ollama](https://ollama.com/download). There is no hosted LLM, API key, login, web deployment, or paid service.

## Try it locally

You need Python 3.11+ and Ollama installed. Ollama must be running. The default model is [`qwen3:4b-instruct`](https://ollama.com/library/qwen3:4b-instruct) (about 2.5 GB to download); other installed tool-calling models may be selected with `--model`.

```bash
# Run from the repository directory. Create a virtual environment (recommended):
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt

# See which models you already have:
ollama list
# Download the default model (only if not installed):
ollama pull qwen3:4b-instruct

# Prepare a local database with clearly fictional sample data:
python scripts/prepare_data.py --source-dir fixtures --policy-json fixtures/demo_policies.json --db data/demo.db
python scripts/check_local.py
python main.py --db data/demo.db
```

Type a question such as *“Quais violões têm até R$ 1000?”* or *“Quais são as regras de devolução?”*. Type `sair` to close. The `scripts/setup_local.py` helper can download the model and prepare the same demo database in one step after you install Ollama and the Python dependencies.

If Ollama is installed but not running, start it through its Windows application or run `ollama serve` in another terminal. Model download requires an internet connection **once**; inference and the customer's messages remain on your machine afterward. The model will use your CPU or compatible GPU. RAM, VRAM and response speed depend on your computer.

### Use the challenge dataset

The original CSVs and internal policy manual were intentionally **not included** in this public repository. If you received the challenge ZIP, import it directly:

```bash
python scripts/import_challenge_zip.py "/path/to/Desafio_Técnico_AI_Engineer_2026.zip" --db data/emporio.db
python main.py --db data/emporio.db
```

On Windows, use a quoted path such as `"C:\Users\You\Downloads\desafio.zip"`. The script locates the six CSVs and policy PDF within the ZIP, creates the database locally, and discards temporary extracted files. The database is ignored by Git.

To run with an **already installed** model instead, pass `--model` to the agent and tools:

```bash
ollama list
python main.py --db data/emporio.db --model qwen3:4b-instruct
python scripts/capture_examples.py --db data/emporio.db --model qwen3:4b-instruct
```

Nothing in this project tries to start Ollama Cloud: the client only accepts a `localhost` or `127.0.0.1` address (the default is `http://127.0.0.1:11434/v1`). No `.env`, API key or cloud subscription is required.

## How it works

```text
Customer -> local Ollama model -> tool call -> Python function
                                          |-> SQLite read-only queries
                                          |-> policy text search
                          <- structured result <-
         <- Portuguese answer <- Ollama
```

- **Tool calling:** the model decides whether to search catalog entries, fetch product details, consult a policy, check promotions, calculate payment options or view an authorized order. The Python functions define what may be accessed. The model never writes SQL.
- **SQLite:** all six supplied CSVs can be imported with schema checks and foreign keys. Product availability requires an active status **and** positive stock. Orders and promotions are static snapshots, not live store systems.
- **Policy retrieval:** the short PDF is extracted by `pypdf` and searched by normalized terms; a vector database would add complexity without a clear benefit for this manual. Results include source pages. It can miss unusual paraphrases.
- **Local model:** Qwen3 4B Instruct was chosen for its modest download size and tool-calling support. A tiny standard-library HTTP client talks only to Ollama's compatible local chat endpoint. No orchestration framework or paid SDK is needed.
- **Conversation state:** the last eight turns are kept in memory during the CLI session. Sessions are not persisted after restart.

### Limits and business rules

The agent cannot buy products, reserve stock, file returns, issue refunds, reach a person or provide live delivery updates; it should never claim those actions succeeded. It is a read-only prototype.

The original data has a few traps: some active products have no stock; active promotions have no explicit start/end dates; the policy document contains competing installment minimums and conflicting contact information. The code applies specific installment rules, never combines promotion and PIX discounts, and does not invent promotion expiry dates or a definitive contact channel when sources disagree.

Order lookup is disabled unless the host supplies a trusted `authenticated_customer_id`. For **local demonstrations only**, `python main.py --db data/demo.db --demo-customer-id 1` simulates an already-authenticated customer. It does **not** authenticate anyone. Never expose this switch through a public web server or use it with real customer data. No personal names or emails are returned by the order tool.

The included `fixtures/` are fictional, not disguised copies of the challenge's customer data. The private policy PDF, customer CSVs, original database and secret files are excluded from version control.

## Tests and example conversations

```bash
python -m pytest -q
python scripts/capture_offline_checks.py

# With Ollama running and your chosen model installed:
python scripts/capture_examples.py --db data/demo.db
python scripts/run_evals.py --db data/demo.db
```

- **pytest** exercises import, SQL restrictions, stock, discounts, payments, retrieval, conversation context, privacy, and tool calling. Some checks against the original private dataset are optional: configure `ARTEFACT_SOURCE_DIR` and `ARTEFACT_POLICY_PDF` to run them. The public fixtures are sufficient for the standard tests.
- **HTTP integration** is tested against a *scripted local server*, to verify actual request/response wiring; it does **not** prove a model ran.
- **Model-backed conversations:** `capture_examples.py` records four actual multi-turn conversations and tool selections to `examples/live_conversations.md`. The script fails rather than inventing a transcript when model execution fails.
- **Local model evaluation:** `run_evals.py` compares tool selection, required answer facts and forbidden claims against `evals/cases.json`, saving a report in `evals/live_results.json`. Models can fail these tests: inspect actual results, rather than assuming a perfect score. These files are produced only after a local inference run.
- `examples/offline_tool_checks.md` documents only deterministic Python tool executions and is **not** a model-backed demonstration.

## Why no web app?

The assignment explicitly accepts a CLI and local models. Requiring a publicly reachable model server would add deployment cost, operational risk and a privacy problem to a read-only prototype. A web UI or a FastAPI wrapper could be added later if there were a real need, but neither would improve the correctness of the underlying agent here.

## AI-assisted development

ChatGPT was used to review the challenge, sketch a small architecture, implement portions of the Python code and tests, and help audit business rules and documentation. Decisions, importer results and test outcomes were checked against the supplied challenge files. Scripted tests are labeled separately from model execution. The candidate should review and be able to explain the code and any recorded local model outputs before submission.
