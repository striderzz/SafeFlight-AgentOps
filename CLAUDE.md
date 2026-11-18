# CLAUDE.md: SafeFlight AgentOps build guide

This file tells Claude (Claude Code) how to build this project. Read **README.md** first: it is the design spec. **INFO.md** (overview, system design, workflows, scoring method) and **INTERVIEW.md** (interview Q&A) are the companions. This file is the build plan.

## Goal

A CrewAI multi-agent research assistant on the Claude API. The user enters origin and destination airports (IATA) and a date. A CrewAI Flow:

- validates input in plain Python;
- runs a **Flight Scout** that finds itineraries with the **operating** carrier per segment, and builds two-ticket connections through hubs with `build_self_transfers`;
- pauses with `@human_feedback` so the user picks what to research;
- runs a **Safety Researcher** (MCP tools over DuckDB + hybrid RAG over NTSB narratives) and an **Airspace Watch** agent (official bulletins + shapely geometry, news as context only) in parallel;
- runs a **Risk Analyst** that gets every number from the deterministic `score_carrier` tool;
- ranks options in code (airspace status, band, price, duration);
- runs a **Travel Advisor** that writes a Pydantic structured recommendation with citations, uncertainty, the separate-ticket warning for self-transfers, and a disclaimer;
- checks it with CrewAI task guardrails: one retry, one Opus escalation, then a template fallback.

Around it: an LLM layer with routing, prompt caching, a Redis semantic cache, cost caps and a fake provider; OpenTelemetry traces and versioned prompts in self-hosted Langfuse; an eval harness with an LLM-as-a-judge calibrated by Cohen's kappa that gates pull requests; Docker, Docker Compose and GitHub Actions CI/CD with images pushed to GHCR.

This is a one-person portfolio project of about four weeks. Keep it at that size. The agentic system is the core; trained ML models, fine-tuning and Kubernetes are stretch goals.

## Tech stack

- Python 3.11 (pip + pinned `requirements.txt` and `requirements-dev.txt`)
- CrewAI 1.8.0 or later (Flows with `@start`, `@listen`, `@router`, `and_`, `@human_feedback`; Crews, Agents, Tasks with `output_pydantic` and guardrails; `BaseLLM`; event listeners)
- crewai-tools with the `mcp` extra (`MCPServerAdapter`), and `SerperDevTool` for news
- Claude through the official `anthropic` SDK, wrapped in a CrewAI `BaseLLM` adapter: `claude-haiku-5-5` (scout, researcher, airspace watch, advisor, judge), `claude-opus-5-5` (analyst, advisor escalation)
- MCP Python SDK (FastMCP, streamable HTTP): `safety-data` and `live-signals` servers
- DuckDB; ChromaDB; sentence-transformers (embeddings and cross-encoder); rank-bm25
- NumPy, SciPy (scoring); shapely, pyproj (geometry)
- Redis with a vector index (exact and semantic cache)
- OpenTelemetry, OpenLIT, Langfuse (self-hosted in Compose)
- FastAPI with Server-Sent Events; SQLite (runs, steps, cost log, CrewAI flow persistence)
- Web app: the existing `web/` (Next.js 15, TypeScript, Tailwind CSS, lucide-react)
- Docker, Docker Compose, Makefile; pytest, ruff, scikit-learn (`cohen_kappa_score`); GitHub Actions; GHCR
- Supporting libraries: pydantic, pydantic-settings, python-dotenv, httpx

## Tools the agents get

| Agent | Model | Tools |
|---|---|---|
| Flight Scout | Haiku | `search_flights` (FlightProvider: fixtures or live adapter), `build_self_transfers`, `recent_route_activity` (live-signals MCP, OpenSky) |
| Safety Researcher | Haiku | `carrier_accidents`, `carrier_exposure`, `aircraft_type_record`, `search_accident_reports` (safety-data MCP) |
| Airspace Watch | Haiku | `conflict_bulletins`, `track_crosses` (safety-data MCP), `search_news` (`SerperDevTool`, context only) |
| Risk Analyst | Opus | `score_carrier` (plain Python function tool) |
| Travel Advisor | Haiku, escalates to Opus | `airport_weather` (live-signals MCP, METAR/TAF); reads `rank_itineraries` output from flow state |

Deterministic code, never an LLM decision: input validation, `score_carrier`, `rank_itineraries`, `build_self_transfers` pairing rules, `track_crosses` and the airspace status, the guardrails, the template fallback.

## Build order (phases)

1. **Scaffold, Docker, CI, LLM layer.** Repo layout from README.md; Dockerfiles in `docker/` for api, safety-data, live-signals and web; `docker-compose.yml` skeleton with Redis; Makefile (`up`, `down`, `test`); `.env.example`; CI (ruff, pytest, web typecheck and build, `docker compose config`) green from day one. `safeflight/llm/`: start with a short spike that a `BaseLLM` subclass on the `anthropic` SDK works with CrewAI agents and tool calling; then routing table, effort set per agent, `stop_reason` checks, prompt-cache breakpoints on stable system prompts and tool schemas, token and USD log per call (including cache tokens) from a price table in config, per-query cap (`LLM_MAX_USD_PER_QUERY`) and monthly cap (`LLM_MONTHLY_BUDGET_USD`), `FakeLLM` and `ReplayLLM`. If the spike fails, fall back to CrewAI's `LLM("anthropic/...")` with `max_tokens` set and usage from its token usage summary, and write the gap down in README.
2. **Data ingestion into DuckDB.** Download scripts for the NTSB database, BTS T-100 segment data and OpenFlights into gitignored `data/`. Ingest into the tables in INFO.md (events, event_aircraft, findings, narratives, t100_segments, airlines, airports, aircraft_types, data_snapshots). Carrier matching: ICAO codes, then an alias table, then fuzzy matching. Data tests: row counts in expected ranges, no orphan keys, the 20 largest carriers mapped, Part 121/129 filter correct. A tiny fixture DuckDB for CI.
3. **Bayesian carrier score.** `safeflight/scoring/` exactly as INFO.md "Scoring method": severity and recency weights, recency-weighted exposure, method-of-moments prior with a maximum-likelihood check, Gamma posterior, 90% interval, shrinkage weight, bands (Strong record, Typical, Higher rate, Limited data). Unit tests against hand-computed values, including the worked example. A sensitivity report on severity weights.
4. **safety-data MCP server and hybrid RAG.** Chunk narratives with metadata into `narrative_chunks`; build the ChromaDB collection and the BM25 index from it; fusion with RRF; cross-encoder rerank. FastMCP server with `carrier_accidents`, `carrier_exposure`, `aircraft_type_record`, `search_accident_reports`, each row with a stable ID. Retrieval eval set (`evals/retrieval.yaml`, about 40 hand-written queries with expected NTSB numbers), reporting hit rate at 5 and MRR for BM25, vectors, hybrid, hybrid + rerank.
5. **Live data and airspace.** `FlightProvider` interface with the fixtures provider (about 25 routes plus hub legs) and one live adapter. Amadeus Self-Service is closing (keys reported disabled July 2026): check Duffel test mode first and accept a provider only if it returns operating carrier and aircraft per segment. `live-signals` FastMCP server: `airport_weather` (aviationweather.gov, custom User-Agent, under its rate limit) and `recent_route_activity` (OpenSky, OAuth2 client credentials). Bulletins: `make bulletins` fetches EASA CZIBs and the FAA prohibitions list, parses IDs, levels, valid-until dates, FIR codes and coordinates into `bulletins` and `zones`, and writes a review report; FIR boundary polygons from an open dataset with its source and licence recorded. `conflict_bulletins` and `track_crosses` on the safety-data server: densified great-circle tracks, metric-projection buffers, antimeridian split, shapely intersection, statuses Avoid / Caution / No advisories with bulletin IDs. Geometry test set `evals/tracks.yaml` with known crossings.
6. **Self-transfer builder.** `build_self_transfers`: hub list in config, detour ratio limit, skip hubs inside Avoid zones, separate one-way searches, pairing rules (both operators Strong record by default, layover 3 to 12 hours, same airport, no Avoid leg), combined band, total time and price, one booking link per leg (airline deep link where it can be built, else the airline home page). Log every rejection reason. Unit tests for each rule and its edge cases (overnight layover, exactly 3 hours, airport change, missing band).
7. **CrewAI agents, tasks and Flow.** Five agents with the tools above; `max_iter` lowered per agent. Flow with typed Pydantic state: `@start` validation, `@router` for invalid input, scout crew, `@human_feedback` confirm step with a custom provider raising `HumanFeedbackPending`, research and airspace listening to the confirmation, ranking on `and_(analysis, airspace)`, advisor with `output_pydantic=Recommendation` and the function guardrail (numbers, citations, order, statuses, Avoid has bulletin ID, self-transfer risk notes, disclaimer) with `guardrail_max_retries=1`, a router to the Opus re-run and then the template fallback. Airspace statuses are copied from `track_crosses` by code; news only fills a "recent reports" note. Flow tests with `FakeLLM`, including pause and resume, escalation and fallback.
8. **LLMOps.** Langfuse services in Compose; OpenLIT plus a CrewAI event listener emitting OpenTelemetry spans for flow methods, agents, tasks, tools, MCP calls and LLM calls, with model, tokens, USD and prompt version as attributes; `CREWAI_DISABLE_TELEMETRY=true`. Prompts in `prompts/`, synced to Langfuse with versions and labels, fetched by label with a local fallback. Redis exact cache and semantic cache (scoped keys, similarity threshold, TTL; airspace never semantically cached). Cost and latency views in Langfuse, and a runs summary endpoint for the web app's Runs page.
9. **API and web wiring.** FastAPI: `POST /search` (202 with run_id), `GET /runs/{id}/events` (SSE from the event listener), `GET /runs/{id}`, `POST /runs/{id}/confirm` (resume). Connect `web/` to the API: keep the types in `web/lib/sample.ts` as the contract, replace sample data with API calls, stream the agent trace over SSE, add the confirm step, add the "Higher rate" band state, and show the sample-data banner only when running on sample data. Run `/unslop` on the main screens, then capture real screenshots into `docs/screenshots/`.
10. **Evals, CI gate and release.** `evals/run_eval.py` over `evals/routes.yaml` (about 25 routes): ranking agreement, citation validity, numeric faithfulness and guardrail path shares, self-transfer rule compliance and warning presence, geometry accuracy and the zero "Avoid without source" check, retrieval metrics, semantic cache hit and false-hit rate, p50/p95 latency, USD per query. Judge on Haiku with the four-item rubric; hand-label about 30 answers; report Cohen's kappa per item. CI: eval-replay on every pull request; eval-gate on prompt, agent, tool and RAG paths with a dollar cap and thresholds against `evals/baseline.json`; release workflow building the four images and pushing them to GHCR; daily bulletin-check workflow that opens an issue on changes. Raw output to `docs/results/`, results table in README, demo GIF.

## Stretch goals

Only after all ten phases are done and the README results are filled from real runs:

- Real ticket purchase for a self-transfer through an order API, test environment only (the original plan named Amadeus Flight Create Orders, which depends on Self-Service access)
- XGBoost per-flight risk model with a LightGBM comparison, time-based split and PR-AUC, tracked in MLflow, explained with SHAP, monitored with Evidently; it complements the Bayesian score and never replaces it
- LoRA/PEFT narrative cause classifier (ModernBERT or DistilBERT, Hugging Face Transformers) vs Claude zero-shot on macro-F1, feeding RAG metadata
- Kubernetes manifests and a Helm chart, tested on a kind cluster in CI
- LangGraph re-implementation compared on the same eval set
- A2A: expose the Risk Analyst with CrewAI's `A2AServerConfig` (`crewai[a2a]`)
- Multi-city routes; airport-risk signals in the score
- Slack bot front end
- IEEE-style write-up

## Working rules for Claude

- Keep the scope at the level in README.md: a portfolio project for a master's graduate with about a year of experience. Do not add components the README does not list. The owner must be able to explain every line in an interview.
- Build **one phase at a time**, in order. Each phase must run end to end, with tests, before the next starts.
- After each phase, update the **Roadmap checklist in README.md**, add a short "How it works" note to `docs/`, and commit with a clear message.
- **Never invent results.** Every number in README.md, INFO.md and INTERVIEW.md (accuracy, kappa, latency, cost, hit rate) must come from a run in this repo, with raw output in `docs/results/`. Until then it stays "—" or `[measured metric]`. Illustrative arithmetic must be labelled as such.
- **Screenshots:** when a phase produces something visible (web app, Langfuse trace, eval report), capture real screenshots into `docs/screenshots/` and embed them in README.md. Never mock them up. Screenshots of the sample-data UI must say so in the caption.
- `web/` already exists on sample data. Do not restyle it or change its look outside Phase 9 work; it follows the unslop skill (`~/.claude/skills/unslop`). Run `/unslop` on the main screens before calling the UI done.
- **Deterministic first.** Numbers, rankings, pairing rules, geometry and airspace statuses come from tested Python. Agents explain; they do not compute or decide these.
- **Official sources decide airspace status.** News can add a dated "recent reports" note and can never set or change a status. Every "Avoid" must carry a bulletin ID and valid-until date.
- **Self-transfers always carry the three risk notes** (missed connection not protected, bags re-checked, transit visa rules). SafeFlight never takes payment or stores card data.
- Data: never commit datasets, indexes or model files; write download scripts and gitignore the data folders. Never scrape Google Flights, Skyscanner or Aviation Safety Network. Record each source's licence or terms in README.
- Keep secrets out of git: `.env` (gitignored) plus a committed `.env.example`. Never log keys.
- Python 3.11+. Dependencies in pinned `requirements.txt` (runtime) and `requirements-dev.txt` (pytest, ruff). Use `ruff` for lint and format, type hints, and `pytest`.
- **LLM rules:**
  - Every LLM call goes through `safeflight/llm/`, which calls Claude through the official `anthropic` SDK.
  - Keys come from `.env` with a committed `.env.example`.
  - Defaults: `claude-haiku-5-5` for scout, researcher, airspace watch, advisor and judge; `claude-opus-5-5` for the analyst and the advisor escalation. Both configurable in `.env`.
  - Set effort explicitly per agent. On Opus 5.5 thinking cannot be disabled and effort defaults to `medium`; forced `tool_choice` (`any` or a named tool) returns a 400, so use structured outputs for JSON. Do not send `temperature`, `top_p` or `top_k`.
  - Check `stop_reason` (including `refusal` and `max_tokens`) before reading a response.
  - Put stable system prompts and sorted tool definitions first and use prompt caching; verify with `cache_read_input_tokens`.
  - Log tokens and USD for every call, and enforce the per-query (`LLM_MAX_USD_PER_QUERY`) and monthly (`LLM_MONTHLY_BUDGET_USD`) caps.
  - Tests use `FakeLLM` or `ReplayLLM`, so CI never needs a key. The only CI job that spends money is eval-gate, limited to relevant paths and capped in USD; it never runs on forks.
  - Set `CREWAI_DISABLE_TELEMETRY=true`.
- `make up` (or `docker compose up -d`) must bring up the full stack locally.
- Keep the GitHub Actions workflows green.
- Do not commit or push unless the owner asks.

## Definition of done

- One-command local stack (`make up`), with every service built from its own Dockerfile
- README has the architecture diagram, setup steps, real screenshots of the live app, a demo GIF and measured results
- CI is green: lint, tests with the fake LLM, eval-replay, eval-gate on relevant changes, images pushed to GHCR from `main`
- Tests cover the core logic: scoring math, ranking, self-transfer rules, geometry, guardrails, flow routing, pause and resume
- The judge's kappa against human labels is reported per rubric item
- The web app has passed an `/unslop` review

## Status

Only `README.md`, `INFO.md`, `INTERVIEW.md`, this file, `LICENSE` and the sample-data front end in `web/` exist so far. Start at **Phase 1**.
