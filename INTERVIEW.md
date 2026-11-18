# SafeFlight AgentOps: interview prep

Companion to [README.md](README.md). This file is for explaining the project out loud: the pitch, how each part works, and the questions interviewers ask. Nothing here is a measured result. The project is designed and being built; every `[measured ...]` blank gets filled from `docs/results/` after real runs. The overview, system design and workflow diagrams are in [INFO.md](INFO.md).

---

## Pitch

### 30-second pitch

"SafeFlight is a multi-agent research assistant I designed and am building with CrewAI on the Claude API. You enter two airports and a date. A Flight Scout finds itineraries and safe two-ticket connections, a Safety Researcher pulls accident data and NTSB reports through MCP tools and hybrid RAG, an Airspace Watch agent checks routes against official conflict-zone bulletins with a geometry check, a Risk Analyst explains a Bayesian safety score that comes from a deterministic tool, and a Travel Advisor writes a cited recommendation. Guardrails reject any number or citation that does not match the data, and a Claude judge calibrated against my own labels gates every pull request in CI."

### 2-minute walkthrough

"The question 'is this airline safe' usually gets answered with rankings that have no sources and no sample sizes. The public data to do better exists: NTSB accident records and narratives, BTS traffic data for exposure, and conflict-zone bulletins from EASA and the FAA. I wanted to build an agent system that joins them carefully, and to measure whether it stays honest.

It is a CrewAI Flow. Input is validated in plain Python first. The Flight Scout, on Claude Haiku, searches flights and records the operating carrier of every segment, because with codeshares the airline that sells the ticket is often not the one flying the plane. It also builds two-ticket connections through hubs, keeping only pairs where both airlines have a strong record, the layover is 3 to 12 hours at the same airport, and no leg crosses an avoid zone. Then the flow pauses with CrewAI's human feedback decorator so the user picks what to research, which is the biggest cost control.

After that, two agents run in parallel. The Safety Researcher calls an MCP server I wrote on DuckDB, plus hybrid search over NTSB narratives: BM25 and vectors fused with reciprocal rank fusion, then a cross-encoder rerank. Airspace Watch gets its statuses from a shapely geometry check against official bulletins; news search only adds a 'recent reports' note and can never mark a route unsafe.

The Risk Analyst on Opus must call a scoring tool. The score is accidents per million departures, with Poisson-Gamma empirical Bayes shrinkage so an airline with a few thousand flights and no accidents is not ranked best, and a 90% credible interval. Ranking is done in code. The Travel Advisor writes a Pydantic structured output, and a CrewAI guardrail checks every number, citation, status and warning. One retry, one escalation to Opus, then a template answer built from the data.

For LLMOps, every call goes through one layer with routing, prompt caching, a Redis semantic cache, per-query and monthly cost caps, and OpenTelemetry traces into a self-hosted Langfuse with versioned prompts. Evals run on 25 recorded routes: ranking agreement, citation validity, rule checks, geometry accuracy, and a Claude judge calibrated with Cohen's kappa. A GitHub Actions gate fails a pull request when scores drop, and images ship to GHCR. Results so far: [measured ranking agreement], [measured guardrail pass rate], judge kappa [measured kappa], [measured USD] per query."

---

## Interview questions with answers

### Project overview

**1. What is SafeFlight, in one or two sentences?**
A CrewAI multi-agent assistant on the Claude API that finds flights for a route, researches each operating airline's public safety record, checks routes against official airspace bulletins, and writes a cited recommendation with honest uncertainty. Every number comes from deterministic code, and guardrails plus a calibrated LLM judge check the words.

**2. Why five agents instead of one agent with every tool?**
One agent with a dozen tools and a long transcript picks tools poorly and mixes sources. Splitting by job keeps each prompt and tool list small, lets research and airspace checks run in parallel, and lets me use Haiku for the tool-heavy work and Opus only for synthesis. The cost is more orchestration, which the Flow keeps explicit. Where a step needs no judgment (scoring, ranking, pairing, geometry) it is a plain function, not an agent.

**3. What did you write yourself and what is off the shelf?**
Off the shelf: CrewAI, the MCP SDK, ChromaDB, DuckDB, shapely, Langfuse, the embedding and reranking models. I wrote the Flow and agent definitions, both MCP servers, the scoring model, the self-transfer builder, the bulletin parser and geometry check, the guardrails and template fallback, the LLM adapter with routing and cost caps, the caches, the eval harness and judge calibration, and the CI workflows. The `web/` front end exists on sample data and gets wired to the API in Phase 9.

### CrewAI and agents

**4. Why CrewAI and not LangGraph?**
CrewAI's agent model (role, goal, backstory, tools, tasks with expected outputs) maps directly onto five specialists, and Flows give me explicit control flow: `@start`, `@listen`, `@router` for branches, `and_` to join parallel branches, typed Pydantic state, and `@human_feedback` for the pause. LangGraph would give finer graph control and a more mature checkpointer. I did not want to argue it in the abstract, so a LangGraph re-implementation measured on the same eval set is a stretch goal.

**5. Walk me through the Flow.**
`validate_input` is the `@start`. A `@router` sends invalid input to a 422 and valid input to the scout crew. The confirm step uses `@human_feedback` and pauses. Two methods `@listen` to the confirmation: research and airspace. Analysis listens to research. Ranking listens to `and_(analysis, airspace)`, so it runs only when both are done. The advisor runs next, and another router sends a failed guardrail to the Opus escalation and then the template fallback.

**6. How does the human confirm step work technically?**
The confirm method is decorated with `@human_feedback` and a custom provider. The provider stores the pending request and raises `HumanFeedbackPending`; CrewAI saves the flow state (SQLite by default) and `kickoff` returns the pending object instead of blocking. The API marks the run "awaiting confirmation" and streams that to the browser. When the user submits, `POST /runs/{id}/confirm` calls `Flow.from_pending(flow_id)` and `await flow.resume_async(feedback)`, and the flow continues. Pending runs expire after a TTL.

**7. How do you stop the Risk Analyst from inventing numbers?**
Three layers. Its task description says every number must come from `score_carrier`, and the tool returns all of them already formatted. Its output is structured, with number fields filled by code from the tool result, not by the model. And the advisor's guardrail checks every number in the final text against the scoring output, so an invented number cannot reach the user.

**8. How does model routing work?**
A routing table in config maps each agent to a model: Haiku for scout, researcher, airspace watch, advisor and judge; Opus for the analyst. Escalation is rule-based, not model-chosen: if the advisor fails its guardrail after one retry on Haiku, the flow re-runs it once on Opus. If the remaining per-query budget cannot cover an Opus call, the run uses the template fallback and says so. Every routing decision is a span attribute, so I can count escalations: [measured escalation rate].

### MCP

**9. Why MCP instead of Python functions, and why two servers?**
MCP gives each data source a process boundary and a standard schema: I test the servers alone, restart them alone, and can use the same tools from Claude Desktop when debugging. `safety-data` is offline and deterministic (DuckDB, ChromaDB, bulletins, geometry); `live-signals` calls the internet and can fail or rate-limit. Keeping them apart keeps failure modes apart. Pure computations with no data boundary, like `score_carrier`, stay plain function tools.

**10. How are MCP tools loaded into CrewAI, and what if a server is down?**
With `MCPServerAdapter` from `crewai-tools[mcp]`, used as a context manager over streamable HTTP, filtered to the tools each agent needs, with a connection timeout. If `live-signals` is down, weather and OpenSky context are marked unavailable and the run continues. If `safety-data` is down, research cannot happen, so the run fails early with a clear message instead of letting the model answer from memory.

### RAG

**11. Walk me through the hybrid retrieval pipeline.**
Metadata filters on carrier, aircraft type and cause first. Then BM25 and vector search each return their top 50. Reciprocal rank fusion merges them by summing 1 / (k + rank), which avoids calibrating BM25 scores against cosine similarities. A cross-encoder then reads each query and chunk pair and reranks the top 20, and the top 5 go to the agent with NTSB numbers attached. BM25 catches exact terms like "rejected takeoff" or a tail number; vectors catch paraphrases.

**12. How do you evaluate retrieval separately from the agent?**
A hand-written set of queries, each with the NTSB report it should find. I report hit rate at 5 and MRR for four variants: BM25 only, vectors only, hybrid, and hybrid plus rerank, so I can show what each stage adds: [measured hit rate and MRR per variant]. If the agent cites the wrong report, this tells me whether retrieval or reasoning failed.

### Scoring and statistics

**13. Explain the Bayesian shrinkage in plain words.**
Each airline's estimate is a weighted average of its own accident rate and the industry rate, and the weight on its own data grows with how many flights it has. An airline with millions of departures is judged mostly on its own record. One with a few thousand departures is pulled close to the industry rate, because zero accidents in a few thousand flights tells you very little. The posterior also gives a credible interval, which the web app draws as a line around the dot.

**14. Why Poisson-Gamma, and how do you fit the prior?**
Accident counts given exposure are naturally Poisson, and the Gamma prior is conjugate, so the posterior is Gamma(alpha + y, beta + E) in closed form: no sampling, fast, and easy to test by hand. I fit alpha and beta by the method of moments across carriers with enough exposure, subtracting the Poisson noise from the variance of raw rates, and check against a maximum-likelihood fit of the negative binomial marginal. A 90% credible interval means a 90% posterior probability that the rate is in the range, given the model and prior.

**15. How did you pick the "Limited data" threshold?**
From the model itself: the shrinkage weight is E / (beta + E). Below 0.5 the prior carries more of the estimate than the carrier's own data, so I call it "Limited data". That ties the threshold to the fitted prior instead of a magic number of flights.

**16. Why does the operating carrier matter so much?**
A ticket sold by one airline is often flown by a partner or a regional subsidiary. Safety records belong to the operator, so the scout stores marketing and operating carrier per segment, and an itinerary takes the band of its weakest operator. OpenSky is used to cross-check that the operator actually flies the route, and a mismatch is flagged.

**17. What is the biggest weakness of the score?**
Coverage. NTSB and T-100 are strongest for flights touching the US. I keep numerator and denominator in the same scope, but a carrier's record at home may be invisible. The design shows this on every result and gives such carriers wide intervals or "Limited data". The weighted Poisson is also an approximation, and the severity weights are judgment calls, so Phase 3 reports how many bands change under other weights.

### Guardrails and structured outputs

**18. How does the guardrail check numbers and citations?**
It is a CrewAI function guardrail that returns `(True, output)` or `(False, error)`. It extracts every number from the advisor's text with a regex, normalizes formatting, and requires each to equal a value in the scoring output, itineraries or weather data at the displayed precision. Every citation ID must be in the run's evidence registry, built from IDs the tools actually returned. It also checks the ranking order, that statuses equal the computed ones, that every "Avoid" cites a bulletin ID, that self-transfers carry their warning, and that the disclaimer is present.

**19. What happens when the guardrail fails, and why not just retry more?**
The error goes back to the agent for one retry (`guardrail_max_retries=1`). Then the flow re-runs the advisor once on Opus. Then a template writes the answer from the data alone. More retries on the same model mostly repeat the same mistake and add cost and latency; a stronger model or a template is a better next step. The web app marks which path produced the answer, and the eval reports the share of each.

**20. Why `output_pydantic`, and what can a schema not enforce?**
A Pydantic `Recommendation` gives typed fields the web app renders directly: ranked options, bands, intervals, citations, risk notes, disclaimer. A schema guarantees shape, not truth: it cannot know whether 0.21 is the real rate or whether an NTSB number exists. That is what the guardrail is for.

### Airspace Watch and self-transfers

**21. How does Airspace Watch decide "Avoid", and why can news never set it?**
Only official sources decide. A refresh job stores EASA Conflict Zone Information Bulletins and FAA prohibitions with their IDs, levels, zones and valid-until dates. `track_crosses` computes whether each segment's track crosses an active zone: prohibition or high-risk level means "Avoid", a lower-level advisory means "Caution". The status field is filled by code. News from `search_news` only adds a dated "recent reports" note, because headlines can be wrong, old or alarmist, and the system must not overreact to them. An eval check requires zero "Avoid" statuses without an official bulletin ID.

**22. How do you compute whether a route crosses a zone, and what are the pitfalls?**
Build the great-circle track for each segment, densify it into points, buffer it in a metric projection (buffers in degrees are wrong away from the equator), split it at the antimeridian, and intersect it with the zone polygons in shapely. Pitfalls: degree buffers, antimeridian wrap, FIR polygons that are simplified or out of date, and the biggest one, that a great circle is not the route airlines fly. So the wording is "the direct track crosses an area in bulletin X, check with the airline". A hand-built track set measures precision and recall: [measured geometry accuracy].

**23. How does `build_self_transfers` work?**
It picks hubs from a config list where the detour ratio is under a limit, skips hubs inside an "Avoid" zone, searches origin to hub and hub to destination as separate one-way legs, and pairs them only when both operators are "Strong record", the layover is 3 to 12 hours, and the second leg leaves from the same airport. Each pair gets the weaker leg's band, total time, total price and one booking link per leg. Every rejection is logged with a reason, so the eval can count them. It is code, not an agent decision, so the rules are testable.

**24. How do you make sure the separate-ticket warning always appears?**
Three ways. The `Recommendation` schema has a `risk_notes` list with fixed codes (missed connection not protected, bags to re-check, transit visa). The guardrail requires all three whenever a self-transfer is suggested. And the judge rubric has an item for whether the warning is clear to a traveller. The eval reports the share of answers with the warning present: [measured warning rate].

### Evals and LLM-as-a-judge

**25. How does the LLM judge work?**
Claude Haiku gets the route data, the advisor's answer and a rubric with four items, each on a 1 to 5 scale with anchored descriptions: clarity, honest uncertainty, the separate-ticket warning when relevant, and neutral, non-alarmist wording. It must quote the text behind each score and returns a structured output. Facts are not judged by the LLM; they are checked by code. The judge only grades what code cannot.

**26. How do you know the judge is right?**
I hand-label about 30 answers on the same rubric and compute Cohen's kappa between my labels and the judge's, per item: [measured kappa per item]. Kappa corrects for chance agreement, which matters when most answers are good. If an item's kappa is below the target, I rewrite the rubric anchors or add examples and re-check, and that item is reported but not gated until it passes.

**27. How does the CI eval gate avoid being flaky or expensive?**
Two jobs. eval-replay runs on every pull request with recorded LLM responses, so it is free and deterministic and runs all the code checks. eval-gate makes live Claude calls only when prompts, agents, tools or retrieval change, under a hard dollar cap, on fixture routes so the inputs never move. Thresholds are set wider than the run-to-run noise I measure on repeated runs of the same commit: [measured noise band]. The baseline in `evals/baseline.json` only changes in a reviewed commit.

**28. What are the results?**
On [N] eval routes: ranking agreement [measured], citation validity [measured], first-attempt guardrail pass rate [measured], template fallback rate [measured], judge scores [measured per item] with kappa [measured], retrieval hit rate at 5 [measured] and MRR [measured], geometry accuracy [measured], p50/p95 latency [measured], and [measured USD] per query. Raw output is in `docs/results/`. The weakest area is [fill in from results], because [fill in].

### Cost and latency

**29. How do you keep cost under control?**
The confirm step limits research to what the user picks. Haiku does the tool-heavy work and Opus is used once per run plus rare escalations. Stable system prompts and tool schemas go first for prompt caching. Tool outputs are summarized in the MCP servers. A Redis semantic cache reuses per-carrier research. Per-query and monthly caps stop spending, and every call logs tokens and USD, so I can see where money goes: [measured USD per query].

**30. How do you know prompt caching and the semantic cache are working?**
For prompt caching, the cost log records `cache_read_input_tokens`; if it stays at zero, something dynamic, like a timestamp or an unsorted tool list, is breaking the prefix. For the semantic cache, the eval reports hit rate and false-hit rate by comparing cached answers with fresh ones on the same inputs: [measured hit and false-hit rates]. Keys are scoped by carrier, data snapshot and prompt version, and airspace results are never semantically cached because bulletins change.

**31. Where does the latency go?**
The trace in Langfuse has a span per flow step, agent, tool and LLM call, so the slowest step is visible per run. The parallel research and airspace branches, the scoring as plain Python, and cached research should keep it down; the expected large items are the Opus synthesis and hub leg searches for self-transfers: [measured p50/p95 and breakdown].

### Data and ethics

**32. Is it responsible to rate airline safety at all?**
Only with care. Commercial aviation is extremely safe and differences between major airlines are small, so most carriers land in "Typical" and the app says so. Every number has a source, every interval is shown, data gaps are labelled, and the disclaimer says this is a summary of public records, not travel or safety advice. Airspace statuses do not replace airline or government decisions, and the judge grades neutral wording.

**33. What data do you use, and what do you refuse to use?**
NTSB accidents and narratives, BTS T-100 for departures, OpenFlights for codes, EASA and FAA bulletins, aviationweather.gov, OpenSky, and a documented search tool for news. Aviation Safety Network is only cited for manual cross-checks because its terms limit scraping. I never scrape Google Flights or Skyscanner, and data folders are gitignored with download scripts instead.

### Deployment and CI/CD

**34. Walk me through the Docker and CI/CD setup.**
One Dockerfile per service: api (FastAPI plus the Flow), safety-data, live-signals and web. Docker Compose runs them with Redis and the Langfuse stack, with health checks and a shared read-only data volume. GitHub Actions runs ruff, pytest with the fake LLM, the web build, `docker compose config` and eval-replay on every pull request; eval-gate on relevant paths; and on `main` builds the four images and pushes them to GHCR tagged with the commit SHA and `latest`, using the built-in `GITHUB_TOKEN`. A scheduled workflow checks bulletin sources daily and opens an issue on changes.

### Scaling and failure modes

**35. Your flight API went away. What did you do?**
The plan named Amadeus Self-Service, and Amadeus announced in February 2026 that it is closing that portal; reports say self-service keys were disabled in July 2026. Because `search_flights` sits behind a `FlightProvider` interface and CI already ran on recorded fixtures, nothing else changed. The live adapter is chosen from what is available, Duffel's test mode being the first candidate, and it is only accepted if it returns the operating carrier and aircraft per segment.

**36. Could someone attack this through news results or accident narratives?**
Yes, both are untrusted text and could contain instructions. Tool output is labelled as data in the prompt, and the agent prompts say to treat it only as evidence. More important, nothing the model reads can change a status, a score or a ranking: those come from code, and the guardrail rejects text that disagrees with them. The worst case is an odd sentence in a "recent reports" note, which is shown as context with its source.

### Debugging scenarios

**37. The advisor keeps citing an NTSB number that does not exist. What do you check?**
First whether the number was ever returned by a tool in that run, using the trace; if not, the model invented it and the guardrail should have caught it, so I check the guardrail's ID regex. If it was returned but from a different chunk, I check whether retrieval returned the right chunk metadata. Then I tighten the prompt to cite only IDs from tool output, add the case to the eval set, and confirm the first-attempt citation validity moves.

**38. A route is marked "Avoid", but airlines fly it every day. What do you check?**
The bulletin first: is it still valid, and is its zone parsed correctly (FIR code, polygon, altitude limits)? Then the geometry: is the buffer in a metric projection, is the antimeridian handled, is the great circle very different from real routes in that region? Often the honest answer is that the direct track does cross the zone and airlines divert around it, which the wording already says. If the parse or geometry was wrong, I add the track to `evals/tracks.yaml` with the right answer.

### Behavioral (STAR outlines)

Fill these with what actually happens during the build. Keep the structure, replace the brackets.

**39. Tell me about a time you cut or reshaped scope.**
- Situation: The design grew to include a trained risk model, a fine-tuned classifier, Kubernetes and A2A, for a four-week solo project.
- Task: Ship an agentic system I could fully explain and measure.
- Action: I kept the core loop (agents, MCP, RAG, deterministic scoring, guardrails, judge-gated evals, Docker and CI/CD) and moved the ML and platform work to stretch goals. [Fill in a specific cut made during the build and why.]
- Result: [measured outcome, for example core finished in N weeks with these metrics].

**40. Tell me about a trade-off between quality and cost, or a bug in your own evaluation.**
- Situation: [for example, the judge rated vague answers highly, or Opus escalation was the largest cost].
- Task: Make the numbers trustworthy without blowing the budget.
- Action: [what you changed: rubric anchors, kappa re-check, a cheaper path, a new eval case].
- Result: [measured before and after, for example kappa from X to Y or USD per query from X to Y].

---

## Resume bullets

Templates only. Fill every bracket from `docs/results/`. The project line on a resume reads: **SafeFlight AgentOps** | Python, CrewAI, Claude API, MCP, RAG, ChromaDB, DuckDB, Redis, Langfuse, OpenTelemetry, FastAPI, Docker, GitHub Actions.

- Built an agentic AI, multi-agent LLM system in Python with CrewAI Flows and the Claude API (5 agents, human-in-the-loop confirmation, Haiku-to-Opus routing) that ranks flights by public safety records using MCP tool servers over DuckDB and a deterministic Bayesian scoring tool, with structured outputs and guardrails reaching [measured metric] numeric faithfulness and [measured metric] citation validity across [N] routes.
- Designed hybrid search RAG over NTSB accident reports (BM25 + embeddings in a ChromaDB vector database + cross-encoder reranking with metadata filters), improving hit rate at 5 from [measured metric] to [measured metric] and MRR from [measured metric] to [measured metric] over vector-only retrieval.
- Set up LLMOps and evals: LLM-as-a-judge rubric calibrated to human labels (Cohen's kappa [measured metric]) as a CI/CD eval gate in GitHub Actions, OpenTelemetry tracing into Langfuse with versioned prompts, a Redis semantic cache and cost caps, holding p95 latency at [measured metric] and cost at [measured metric] USD per query; shipped with Docker, Docker Compose, FastAPI and GHCR images.

---
