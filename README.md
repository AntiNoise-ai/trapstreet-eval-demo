# trapstreet-eval-demo

> **Does this agent actually get the job done?**
> See how Claude does on real SEC 10-K extraction questions, curated by
> AntiNoise's [market-research](https://github.com/AntiNoise-ai/market-research).
> Cases come from [FinanceBench](https://huggingface.co/datasets/PatronusAI/financebench).

There are two ways to run this:

| | **Skill** (recommended) | **Repo** (advanced) |
|---|---|---|
| Setup | One `curl` line | `git clone` + Python venv |
| Time to first score | ~30 sec | ~2-3 min |
| What you test | Your local Claude (this session) | Claude / GPT-4o / your own agent, head-to-head |
| Questions | 5 (evidence inline) | 15 (evidence + full PDF mode) |
| Auth | None — uses your Claude Code session | Claude Code session **or** `ANTHROPIC_API_KEY` |
| Cost | $0 (Claude subscription) | $0–$0.20 |

---

## ⚡ Quick demo — Claude Code skill

If you have [Claude Code](https://claude.ai/code) installed, this is the
fastest possible loop. Install once:

```bash
curl -fsSL https://raw.githubusercontent.com/AntiNoise-ai/trapstreet-eval-demo/main/skill/install.sh | bash
```

Then in **any** Claude Code session:

```
> /trapstreet-eval
```

Claude reads the 5 bundled questions, answers each one (closed-book —
evidence only, no web search), grades against the gold key with a
deterministic numeric matcher, and prints a leaderboard. ~30 seconds, $0.

That's the AntiNoise eval shape compressed into a single conversational
turn — useful for a "show, don't tell" demo, but not a benchmark you can
publish (Claude is graded against itself; no GPT/Haiku comparison; only 5
questions).

For real numbers, use the repo below.

---

## 🏁 Full demo — clone the repo

The repo path tests **multiple agents** on **15 questions**, supports both
evidence and PDF modes, and lets you plug in your own agent for the
leaderboard:

```bash
git clone https://github.com/AntiNoise-ai/trapstreet-eval-demo.git
cd trapstreet-eval-demo
./scripts/run_demo.sh                         # ~2 min, $0 on Claude subscription
```

When it's done, open [`results/compare.md`](results/) — that's your leaderboard.

---

## The backstory (why this case)

Trapstreet's positioning isn't another model leaderboard — it's a
**"does this thing actually get my job done"** leaderboard. That positioning
forced a question: *what jobs?*

So we ran our own market research with an AI agent to find out. The output is
in [`AntiNoise-ai/market-research`](https://github.com/AntiNoise-ai/market-research),
specifically [`workflow-eval-platform-test-case-research.md`](https://github.com/AntiNoise-ai/market-research/blob/main/workflow-eval-platform-test-case-research.md):
five Tier-1 candidate tasks, each scored 1–5 on Demand / Data / Eval / Traffic.

This demo runs the top-scoring task: **T1-A — extract specific numbers from
SEC 10-K filings**. Score 20/20.

| Dimension | Score | Why |
|---|---|---|
| **Demand** | 5/5 | Every analyst, VC, fintech and finance-Reddit user types this query daily |
| **Data** | 5/5 | SEC EDGAR + 150 FinanceBench questions, free + redistributable |
| **Eval** | 5/5 | Numeric exact-match (with tolerance) — no fuzzy LLM judging needed for most |
| **Traffic** | 5/5 | "GPT-4-Turbo got **81% wrong**" was the original FinanceBench headline |

So: we built the eval platform, then used the eval platform's logic to pick
its first test case. This repo is the simplest end-to-end shape of that.

---

## How to run

The demo runs **on your machine**. No login, no upload, no remote service.

### Auth — pick one (in order of preference)

| You have… | What happens | Cost |
|---|---|---|
| Claude Code (`claude` CLI on PATH, logged in) | Default. The runner shells out to `claude -p` with your session. | **$0** if you're on a Claude subscription — usage counts against your plan. |
| `ANTHROPIC_API_KEY` only | Falls back to the Anthropic SDK. | ~$0.05–$0.20 per full run (15 questions × ~3 baselines). |
| `OPENAI_API_KEY` (optional) | Required only if you add `gpt-4o` to the agent list. | OpenAI's standard rates. |

If you only have Claude Code, you don't need to touch `.env` at all — just run.

### Run

```bash
./scripts/run_demo.sh                         # default: evidence mode, naive + claude
```

Or pick agents and mode explicitly:

```bash
AGENTS=naive,claude,claude-haiku,gpt-4o  MODE=pdf  ./scripts/run_demo.sh
LIMIT=5  MODE=pdf  ./scripts/run_demo.sh      # quick 5-question sanity run
```

### Where to see the score

The script prints the leaderboard to stdout when it finishes, and writes:

| File | What's in it |
|---|---|
| `results/compare.md` | **Human-readable leaderboard** — open this. Per-agent accuracy, latency, cost, plus a "where they disagree" diff table. |
| `results/compare.json` | Same data in JSON — every question, every agent's prediction, every grade reason. For scripting / dashboards. |
| `results/<agent>.md` | Per-agent detail — full per-question table for `claude`, `gpt-4o`, etc. |
| `results/<agent>.json` | Same, JSON. |

Sample `compare.md`:

```
| Agent             | Accuracy   | Latency p50 | Latency p95 | Cost    |
|-------------------|------------|-------------|-------------|---------|
| claude-sonnet-4-6 | 13/15 (87%)| 4.2s        | 7.1s        | $0.0234 |
| gpt-4o            | 11/15 (73%)| 6.8s        | 11.4s       | $0.0612 |
| claude-haiku-4-5  | 10/15 (67%)| 1.9s        | 3.4s        | $0.0041 |
| naive             | 0/15  (0%) | 0ms         | 0ms         | $0.00   |
```

---

## Two modes

### `MODE=evidence` (default — fast, cheap, ~30s)

Each agent receives the **gold evidence passage** that contains the answer.
This isolates extraction quality from retrieval. Most agents score in the
80-95% range here. Useful as a sanity check and for cheap iteration.

### `MODE=pdf` (real — slower, more honest, ~3 min on first run)

Each agent receives the **full 10-K filing text** (extracted from the PDF).
Now they need to find the right paragraph *and* extract correctly. This
matches the original FinanceBench task — which is where the
"GPT-4-Turbo gets 81% wrong" stat comes from.

First run downloads ~10-50MB of PDFs from
[`patronus-ai/financebench/pdfs`](https://github.com/patronus-ai/financebench/tree/main/pdfs)
into `data/financebench/pdfs/` — only the ones the subset needs. Extracted
text is cached at `data/financebench/pdf_text/`, so re-runs reuse it.

---

## Plug in your own agent

Edit [`trapstreet_eval/agents/your_agent.py`](trapstreet_eval/agents/your_agent.py):

```python
from .base import Agent, AgentResponse, QuestionContext

class YourAgent(Agent):
    name = "your-agent"

    def answer(self, ctx: QuestionContext) -> AgentResponse:
        # ctx.mode        — 'evidence' or 'pdf'
        # ctx.question    — the FinanceBench question
        # ctx.evidence    — tuple of gold passages (evidence mode)
        # ctx.pdf_text    — full 10-K text (pdf mode)
        # ctx.pdf_path    — Path to the PDF file (pdf mode)
        # ctx.company, ctx.doc_name, ctx.doc_type, ctx.doc_period
        ...
        return AgentResponse(answer="…", latency_ms=…, cost_usd=…)
```

Then:

```bash
./.venv/bin/python -m trapstreet_eval.runner compare \
    --agents claude,your-agent --mode pdf
```

Your agent shows up on the leaderboard alongside Claude and GPT-4o.

---

## How grading works

[`trapstreet_eval/grader.py`](trapstreet_eval/grader.py) tries three things in
order:

1. **Numeric normalize** — parses `"$1.2 billion"`, `"$1,200,000,000"`,
   `"1.2B"`, `"(123)"`, `"12.5%"` to canonical floats; compares with 1%
   relative tolerance.
2. **String match** — for yes/no and short qualitative answers.
3. **LLM judge fallback** — Haiku-backed, only fires when the first two fail.
   Tiny prompt, fractions of a cent. Disable with `--no-judge`.

Mirrors the FinanceBench paper's grading approach with cheaper defaults.

---

## Architecture

```
                    ┌─────────────────────────────┐
   subset.jsonl ──▶ │     trapstreet_eval         │ ──▶ results/compare.md
   (15 questions)   │  ┌────────────────────────┐ │     results/compare.json
                    │  │ runner.py              │ │     results/<agent>.{md,json}
                    │  │  ↓                     │ │
   PDFs ─────────▶  │  │ pdf_utils.py           │ │
   (on demand)      │  │  ↓                     │ │
                    │  │ agents/                │ │
   evidence ─────▶  │  │   naive · claude       │ │
                    │  │   gpt-4o · your-agent  │ │
                    │  │  ↓                     │ │
                    │  │ grader.py              │ │
                    │  │  ↓                     │ │
                    │  │ report.py              │ │
                    │  └────────────────────────┘ │
                    └─────────────────────────────┘
```

---

## Repo layout

```
trapstreet-eval-demo/
├── skill/                      # Claude Code skill — ⚡ quick-demo path
│   ├── install.sh              # One-line install to ~/.claude/skills/
│   └── trapstreet-eval/
│       ├── SKILL.md            # Instructions Claude follows for /trapstreet-eval
│       ├── questions.json      # 5 hand-picked questions with inline evidence
│       └── grade.py            # Stdlib-only numeric+string grader (~80 lines)
├── trapstreet_eval/            # Python harness — 🏁 full leaderboard path
│   ├── agents/
│   │   ├── base.py             # Agent contract + QuestionContext
│   │   ├── naive.py            # Sanity baseline (always answers "0")
│   │   ├── claude.py           # Anthropic baseline (CLI or API; evidence + pdf)
│   │   ├── openai_baseline.py  # OpenAI baseline (evidence + pdf, with truncation)
│   │   └── your_agent.py       # ← your code goes here
│   ├── data.py                 # Load + sample FinanceBench
│   ├── pdf_utils.py            # Download + extract + cache PDFs
│   ├── grader.py               # Numeric + string + LLM-judge grading
│   ├── runner.py               # CLI: run / compare / report
│   └── report.py               # Markdown + JSON renderers
├── scripts/
│   ├── fetch_financebench.sh   # Pull questions JSONL (~900KB)
│   └── run_demo.sh             # One-shot: deps + data + run + report
├── data/                       # gitignored — populated at runtime
└── results/                    # gitignored — populated by each run
```

---

## License

- **Code**: MIT
- **Data**: CC-BY-NC-4.0 by PatronusAI — non-commercial use only.
  See [`LICENSE`](LICENSE) and the
  [dataset card](https://huggingface.co/datasets/PatronusAI/financebench).
