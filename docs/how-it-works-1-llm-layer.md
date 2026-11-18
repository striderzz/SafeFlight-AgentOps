# How it works: scaffold and LLM layer (Phase 1)

## One door for every Claude call

`safeflight/llm/claude.py` defines `ClaudeLLM`, a subclass of CrewAI's native Anthropic provider (the official `anthropic` SDK underneath). CrewAI keeps doing what it does well: message formatting and the tool-calling loop. SafeFlight adds one interception point around the SDK client, so every request and response passes through the same code:

**Before the call**
- Spend caps: `Ledger.check_budget()` blocks the call if the current run (one user query) or the calendar month has reached its cap (`LLM_MAX_USD_PER_QUERY`, `LLM_MONTHLY_BUDGET_USD`).
- `prepare_request()` (a pure function with its own tests) adjusts the request for current Claude models:
  - sets `output_config.effort` per agent role, because Opus 5.5 and Haiku 5.5 default to `medium`;
  - adds top-level `cache_control` so the stable prefix (system prompt, tools, earlier turns) is cached across an agent's tool-calling turns;
  - moves CrewAI's deprecated beta `output_format` into the GA `output_config.format`;
  - removes `temperature`, `top_p` and `top_k`, which current models reject;
  - relaxes forced `tool_choice` (`any` or a named tool) to `auto`, because Opus 5.5 returns a 400 for it;
  - on Opus 5.5, turns on the server-side refusal fallback (`fallbacks: "default"`).

**After the call**
- Tokens are logged per call to SQLite (`llm_calls`), including cache reads and writes, with the USD cost from `prices.py`, the run id, the agent role, the stop reason and the latency.
- `stop_reason` is checked: `refusal` raises `LLMRefusal` (with its category) and `max_tokens` raises `LLMTruncated`, so a declined or cut-off answer is never passed on as if it were complete.

## Routing

`routing.py` maps each agent role to a model, an effort level and `max_tokens`: Haiku 5.5 for the scout, researcher, airspace watch, advisor and judge; Opus 5.5 for the analyst and for re-running the advisor when its guardrail fails.

One compatibility fix: CrewAI's provider only uses native structured outputs for models on its own list and otherwise forces a tool call. Every current model supports structured outputs, so `claude.py` routes Haiku 5.5, Sonnet 5.5 and Opus 5.5 through the native path.

## Tests without a key

- `FakeLLM` plays a fixed script; `ReplayLLM` replays recorded responses keyed by a hash of the messages (and records new ones when given a real LLM).
- `tests/integration/test_crewai_agent.py` runs a real CrewAI agent, task and crew with `FakeLLM`: the agent calls a tool and answers with its result.
- `tests/unit/test_claude_llm.py` runs `ClaudeLLM` against a fake SDK client and checks the request it sends, the cost it logs, refusals, truncation and the budget cap.
- `tests/integration/test_live_claude.py` is the live spike on the real API (a CrewAI agent with `ClaudeLLM` calling a tool). It runs only when `ANTHROPIC_API_KEY` is set and has not been run yet.

## Services

Each service has its own Dockerfile in `docker/`: the API (FastAPI, health check only so far), the `safety-data` and `live-signals` MCP servers (FastMCP over streamable HTTP, one `server_info` tool each until Phases 4 and 5), and the web app (Next.js standalone). `docker-compose.yml` adds Redis Stack for the semantic cache in Phase 8. CI lints, runs the tests with `FakeLLM`, typechecks and builds the web app, validates the Compose file and builds every image.
