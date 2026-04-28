---
name: trapstreet-eval
description: Quick FinanceBench eval — see how well Claude (your local session) answers 5 SEC 10-K extraction questions, curated by AntiNoise's market research. ~30 seconds, no setup, no API key, no upload. Use when the user types `/trapstreet-eval` or asks to "run the trapstreet eval", "try the financebench demo", or similar.
---

# Trapstreet eval — quick demo

When the user invokes this skill, run the steps below in order. Be terse —
this is a demo, not a tutorial. The whole flow should take ~30 seconds.

## Step 0 — Locate the bundled files

Files live alongside this `SKILL.md`:
- `questions.json` — 5 FinanceBench questions with gold answers and evidence
- `grade.py` — deterministic numeric+string grader (stdlib only)

Use the absolute path of this skill's directory. On macOS / Linux that's
typically `~/.claude/skills/trapstreet-eval/`.

## Step 1 — Greet and frame (one sentence)

Print exactly:

```
Trapstreet — does this agent actually get the job done?
5 SEC 10-K questions from FinanceBench, curated via AntiNoise's market research:
https://github.com/AntiNoise-ai/market-research
Running you (this Claude session) as the agent. ~30 seconds.
```

## Step 2 — Load questions

Read `questions.json` from the skill directory. It's a JSON array; each item has
`id`, `company`, `doc`, `question`, `evidence`, `gold`.

## Step 3 — Answer each question

For each question, in order:

1. Read `question` and `evidence` carefully.
2. Compute the answer **using only the evidence** — return a number, percentage,
   currency amount, or short phrase. No explanation, no reasoning shown.
3. Check the answer with the bundled grader:
   ```bash
   python3 "<skill_dir>/grade.py" "<your_answer>" "<gold>"
   ```
   The script exits 0 if correct, 1 if wrong. Stdout shows `CORRECT` or
   `WRONG (...)`. Quote both args properly to handle `$`, parens, and spaces.
4. Track the verdict.

## Step 4 — Render the leaderboard

After all 5 questions, print a markdown table to the user:

```
## Trapstreet Eval — Claude (your local session)

| # | Company   | Question                                   | Gold       | Your answer | ✓ |
|---|-----------|--------------------------------------------|------------|-------------|---|
| 1 | Netflix   | FY2017 total current liabilities (USD M)…  | $5466.00   | $5466       | ✅ |
| 2 | AES       | …                                          | -0.02      | -0.02       | ✅ |
| 3 | 3M        | …                                          | $8.70      | 8.71        | ❌ |
| 4 | Walmart   | …                                          | 42.69      | 42.69       | ✅ |
| 5 | Block     | …                                          | 1.73       | 1.73        | ✅ |

**Score: 4/5 (80%)**
```

Truncate question text to ~50 chars to keep the table readable.

## Step 5 — Closing pitch (one block)

Print this verbatim:

```
─────────────────────────────────────────────────────────────────────────
That's the AntiNoise eval pattern in 30 seconds:
  - real test cases (curated, not synthetic)
  - real grader (numeric tolerance + string match, no LLM judge needed here)
  - real numbers (your Claude vs. the gold answer key)

Next steps:
  • Test your own agent (or compare to GPT-4o, Haiku, etc.):
    git clone https://github.com/AntiNoise-ai/trapstreet-eval-demo
  • Full FinanceBench (PDF mode, 15+ questions, vendor head-to-head):
    cd trapstreet-eval-demo && MODE=pdf ./scripts/run_demo.sh
─────────────────────────────────────────────────────────────────────────
```

## Step 6 — Offer to submit to the public leaderboard

After the closing pitch, ask the user exactly:

```
Submit this run to the trapstreet.run leaderboard? [y/N]
```

Then **stop and wait for the user's reply.** Do not move to Step 7 until
the user answers.

- If their reply starts with `n` / `N`, or is empty → say nothing more, end.
- If their reply starts with `y` / `Y` → continue to Step 7.

## Step 7 — Show payload, attempt submission, fall back gracefully

### 7a. Show what would be sent

Print:

```
Trapstreet would attach the following metadata to your submission:
  case            financebench-t1a-skill-bundle
  score           <N>/5
  per_question    [{id, verdict, given, gold}, ...]
  submission_source  skill (trapstreet-eval)
  skill_version   trapstreet-eval@2026-04
  ts              <UTC now>

Never sent: question text outside this case, your prompts to Claude,
files outside the run, IP address.

Confirm? [y/N]
```

Stop and wait. If the user does not confirm, end here.

### 7b. Attempt the POST

If they confirm, run this curl exactly. The endpoint **does not exist
yet** — the call will fail until the v1 backend ships. That is expected.

```bash
curl -fsS -m 5 \
  -X POST https://trapstreet.run/api/submission \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "financebench-t1a-skill-bundle",
    "submission_source": "skill",
    "score": <N>,
    "total": 5,
    "per_question": [{"id": "...", "verdict": "correct|wrong", "given": "...", "gold": "..."}],
    "skill_version": "trapstreet-eval@2026-04",
    "ts": "<ISO 8601 UTC>"
  }' \
  2>&1
```

### 7c. Render the result

If `curl` exit status is **non-zero** (today and through May 28), print
this block verbatim:

```
─────────────────────────────────────────────────────────────────────────
🐟 The submission API ships with the May 29 launch.
   Your local verdict above stands — same grader, same numbers, every time.

   Want a notification when the public leaderboard goes live?
   → Join the waitlist:  https://trapstreet.run/submit

   Why this run is reproducible: the grader is just `grade.py` shipped
   in this skill, no API key, no LLM judge. Re-run the skill any time,
   you get the same number.
─────────────────────────────────────────────────────────────────────────
```

If `curl` exit status is **zero** (post-launch path), print:

```
✅ Submitted. View at https://trapstreet.run/u/<handle>/runs/<run_id>
```

Parse `<handle>` and `<run_id>` from the JSON response if available. If
the response shape isn't recognisable, just print:

```
✅ Submitted to https://trapstreet.run.
```

## Notes for Claude

- **Do NOT search the web** to answer — only use the evidence text in `questions.json`.
  This is a closed-book extraction test.
- **Do NOT show your reasoning** in the per-question step — just produce the
  answer and grade it. Reveal everything only in the final table.
- **Keep the grader deterministic**: always shell out to `grade.py`. Don't
  try to grade in your head — that defeats the demo's reproducibility claim.
- The story matters: cases come from
  [`AntiNoise-ai/market-research`](https://github.com/AntiNoise-ai/market-research)'s
  `workflow-eval-platform-test-case-research.md`, T1-A. Mention it when relevant.
