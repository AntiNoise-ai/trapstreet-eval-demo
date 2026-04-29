---
name: trapstreet-eval
description: Closed-book model eval — fetches a Trapstreet case by ID from Hugging Face, hands each question to Claude (your local session) with no tools, grades the answer, and optionally submits to the public leaderboard at https://trapstreet.run/financebench/. Use when the user types `/trapstreet-eval [case-id]` (defaults to `financebench-1`), or asks to "run the trapstreet eval", "test Claude on financebench", "model eval", and similar.
---

# Trapstreet eval — model eval (closed-book, in-session)

This is the **model eval** path: hand the model exactly the right document
plus the question, no tools, and see if it answers correctly. Sister to
the agent-eval CLI (`trapstreet eval` in a terminal), which gives the
agent tools and lets it do retrieval. Both write to the same leaderboard
at <https://trapstreet.run/financebench/>.

When the user invokes `/trapstreet-eval [case-id]` (default `financebench-1`):

## Step 1 — Greet (one short block)

```
Trapstreet — model eval mode.
Case: <case-id>. Fetching from Hugging Face…
```

## Step 2 — Fetch the case from Hugging Face

Use Bash:

```bash
CASE_ID="<case-id>"  # whatever the user passed; default financebench-1
HF_BASE="https://huggingface.co/datasets/Ruqii/trapstreet-cases/resolve/main"
mkdir -p /tmp/trapstreet-eval
curl -fsSL "$HF_BASE/cases/$CASE_ID/task.json" -o /tmp/trapstreet-eval/task.json
```

Read `/tmp/trapstreet-eval/task.json`. It has:
- `id`, `type`, `version`, `doc_files`
- `questions`: array of `{ id, question, gold, expected_correct_doc }`

## Step 3 — For each question, fetch only its correct doc and answer

Closed-book means the model gets ONLY the relevant doc plus the question.
For each question `q` in `task.questions`, in order:

1. Fetch `q.expected_correct_doc`:
   ```bash
   curl -fsSL "$HF_BASE/cases/$CASE_ID/docs/<q.expected_correct_doc>" \
     -o /tmp/trapstreet-eval/doc.txt
   ```
2. Read `/tmp/trapstreet-eval/doc.txt` and `q.question` carefully.
3. Compute the answer **using only that document text**. No web search,
   no other context, no reasoning shown to the user — just produce the
   answer (a number, percentage, currency amount, or short phrase).
4. Grade with the bundled grader:
   ```bash
   python3 ~/.claude/skills/trapstreet-eval/grade.py "<your_answer>" "<q.gold>"
   ```
   Exit 0 = correct, exit 1 = wrong. Stdout shows `CORRECT` or `WRONG (...)`.
5. Track `{id, given, gold, verdict}` in a per-question list.

## Step 4 — Render the leaderboard table

After all questions, print a markdown table:

```
## Trapstreet Eval — Claude (model eval, no tools)
Case: <case-id>

| # | Question (truncated)                          | Gold       | Your answer | ✓ |
|---|-----------------------------------------------|------------|-------------|---|
| 1 | …                                             | …          | …           | ✅ |
| ... |

**Score: <N>/<M> (<pct>%)**
```

Truncate question text to ~50 chars for readability. Score header should
also list the case id.

## Step 5 — Comparison pitch (one block)

```
─────────────────────────────────────────────────────────────────────────
That's the MODEL eval — closed-book, no tools, just the right document.

Want to see how an AGENT does on the same case (with retrieval, tool use,
multi-step)? Install the trapstreet CLI and try it:

  curl -fsSL https://trapstreet.run/install.sh | bash
  export ANTHROPIC_API_KEY=sk-ant-...
  trapstreet eval <case-id>

Same leaderboard, side-by-side. Cases live on Hugging Face:
  https://huggingface.co/datasets/Ruqii/trapstreet-cases
─────────────────────────────────────────────────────────────────────────
```

## Step 6 — Offer to submit

Ask the user exactly:

```
Submit this run to https://trapstreet.run/financebench/? [y/N]
```

Stop and wait. If their reply doesn't start with `y`/`Y`, end here.

## Step 7 — Collect submission metadata

Ask the user (one prompt at a time):

```
Handle for the leaderboard (1–40 chars):
```

Then optionally:

```
GitHub username (optional, for avatar):
```

Empty answer = skip that field.

## Step 8 — POST to Supabase

Build the payload. `case_id` is whatever the user invoked (`financebench-1`
by default). `score`/`total` come from Step 3. `given` and `gold` are
compact summaries: `"<q1.id>=<q1.given> | <q2.id>=<q2.given> | ..."` etc.
`verdict` is `"correct"` if score == total, else `"wrong"`.

```bash
SUPABASE_URL="https://cbqzjwdviifvwlpwsjdm.supabase.co"
SUPABASE_ANON_KEY="sb_publishable_k6C9lKKuF0097AHDvGYnPw_E7QWv2mW"

# Pre-build the JSON payload as a heredoc, then post it.
PAYLOAD=$(cat <<'JSON'
{
  "handle": "<user-handle>",
  "case_id": "<case-id>",
  "agent_label": "claude-direct (in-session, model-eval)",
  "score": <N>,
  "total": <M>,
  "given": "<compact summary>",
  "gold": "<compact summary>",
  "verdict": "<correct|wrong>",
  "tier": "bronze",
  "fabrications": 0,
  "cost_usd": 0,
  "latency_ms": 0,
  "patch": "claude-opus-4-7 (Claude Code session, no tools)"
  /* if github username supplied: */
  , "github_handle": "<github>"
}
JSON
)

curl -fsS -X POST "$SUPABASE_URL/rest/v1/runs" \
  -H "Content-Type: application/json" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Prefer: return=representation" \
  -d "$PAYLOAD"
```

If `github_handle` is empty, omit it from the JSON entirely.

## Step 9 — Render the result

If the curl succeeds (exit 0):
```
✅ Submitted. See your row at https://trapstreet.run/financebench/
```

If it fails:
```
❌ Submission failed: <error from curl/response>.
   Local verdict above stands — same grader, same numbers, every time.
```

## Notes for Claude

- **Do NOT search the web** for answers. Only use the doc text fetched from HF.
- **Do NOT show your reasoning** in Step 3 — just produce the answer.
- **Always grade via `grade.py`** — never grade by inspection. The deterministic
  grader is the whole reproducibility claim.
- The published Supabase URL + key in Step 8 are public-by-design (RLS on the
  server gates writes). Don't worry about them being in this file.
- Sister flow (agent eval, with tools) is the trapstreet CLI:
  `curl -fsSL https://trapstreet.run/install.sh | bash` → `trapstreet eval <case-id>`.
