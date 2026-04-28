"""Run agents against the FinanceBench demo subset and write JSON + Markdown reports.

CLI:
    python -m trapstreet_eval.runner run --agent claude
    python -m trapstreet_eval.runner run --agent claude --mode pdf --limit 3
    python -m trapstreet_eval.runner compare --agents naive,claude,gpt-4o --mode pdf
    python -m trapstreet_eval.runner report
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable

from .agents import Agent, QuestionContext, load_agent
from .data import Question, load_subset
from .grader import GradeResult, grade
from .pdf_utils import ensure_pdfs, extract_text
from .report import render_compare, render_run

_REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = _REPO_ROOT / "results"

try:
    from dotenv import load_dotenv
    # Pin to the repo-local .env only — never inherit from parent dirs.
    _local_env = _REPO_ROOT / ".env"
    if _local_env.exists():
        load_dotenv(_local_env, override=False)
except ImportError:
    pass


def _build_contexts(questions: list[Question], mode: str) -> dict[str, QuestionContext]:
    """Construct one QuestionContext per question, preparing PDF text once if needed."""
    ctxs: dict[str, QuestionContext] = {}
    pdf_text_cache: dict[str, str] = {}

    if mode == "pdf":
        print(f"→ Ensuring PDFs for {len(questions)} questions…", file=sys.stderr)
        ensure_pdfs(questions)
        print("→ Extracting text (cached on disk after first run)…", file=sys.stderr)
        for q in questions:
            if q.doc_name in pdf_text_cache:
                continue
            pdf_text_cache[q.doc_name] = extract_text(q.pdf_path, q.pdf_text_path)

    for q in questions:
        ctxs[q.id] = QuestionContext(
            question=q.question,
            company=q.company,
            doc_name=q.doc_name,
            doc_type=q.doc_type,
            doc_period=q.doc_period,
            mode=mode,
            evidence=q.evidence if mode == "evidence" else (),
            pdf_path=q.pdf_path if mode == "pdf" else None,
            pdf_text=pdf_text_cache.get(q.doc_name, ""),
        )
    return ctxs


def run_one(
    agent: Agent,
    questions: list[Question],
    contexts: dict[str, QuestionContext],
    *,
    mode: str,
    use_judge: bool = True,
) -> dict:
    """Run `agent` on every question and grade. Returns a result dict ready to dump."""
    rows = []
    correct = 0
    cost_usd = 0.0
    latencies: list[int] = []

    for q in questions:
        resp = agent.answer(contexts[q.id])
        g: GradeResult = grade(resp.answer, q.answer, q.question, use_judge=use_judge)
        if g.correct:
            correct += 1
        cost_usd += resp.cost_usd
        latencies.append(resp.latency_ms)
        rows.append({
            "id": q.id,
            "company": q.company,
            "doc": q.doc_name,
            "question": q.question,
            "gold": q.answer,
            "predicted": resp.answer,
            "correct": g.correct,
            "grade_method": g.method,
            "grade_detail": g.detail,
            "latency_ms": resp.latency_ms,
            "cost_usd": resp.cost_usd,
            "error": resp.error,
        })

    total = len(questions)
    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0

    return {
        "agent": agent.name,
        "mode": mode,
        "total": total,
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "cost_usd": round(cost_usd, 4),
        "rows": rows,
        "ts": int(time.time()),
    }


def _ensure_results_dir() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def cmd_run(args: argparse.Namespace) -> int:
    questions = load_subset()
    if args.limit:
        questions = questions[: args.limit]
    contexts = _build_contexts(questions, args.mode)

    agent = load_agent(args.agent)
    print(
        f"Running {agent.name} on {len(questions)} questions (mode={args.mode})…",
        file=sys.stderr,
    )
    result = run_one(agent, questions, contexts, mode=args.mode, use_judge=not args.no_judge)

    out_dir = _ensure_results_dir()
    safe_name = agent.name.replace("/", "_")
    (out_dir / f"{safe_name}.json").write_text(json.dumps(result, indent=2))
    md = render_run(result)
    (out_dir / f"{safe_name}.md").write_text(md)

    print(md)
    print(f"\n✓ Wrote results/{safe_name}.json and results/{safe_name}.md")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    questions = load_subset()
    if args.limit:
        questions = questions[: args.limit]
    contexts = _build_contexts(questions, args.mode)

    agent_names = [a.strip() for a in args.agents.split(",") if a.strip()]
    results = []
    for name in agent_names:
        try:
            agent = load_agent(name)
        except Exception as e:
            print(f"  skip {name}: {e}", file=sys.stderr)
            continue
        print(
            f"Running {agent.name} on {len(questions)} questions (mode={args.mode})…",
            file=sys.stderr,
        )
        results.append(
            run_one(agent, questions, contexts, mode=args.mode, use_judge=not args.no_judge)
        )

    if not results:
        print("No agents ran. Check API keys / agent names.", file=sys.stderr)
        return 1

    out_dir = _ensure_results_dir()
    combined = {"agents": results, "mode": args.mode, "ts": int(time.time())}
    (out_dir / "compare.json").write_text(json.dumps(combined, indent=2))

    md = render_compare(results)
    md_path = out_dir / "compare.md"
    md_path.write_text(md)

    print(md)
    print(f"\n✓ Scores: results/compare.md  (raw JSON: results/compare.json)")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Re-render the comparison from existing per-agent JSON in results/."""
    out_dir = _ensure_results_dir()
    runs = []
    for p in sorted(out_dir.glob("*.json")):
        if p.name == "compare.json":
            continue
        runs.append(json.loads(p.read_text()))
    if not runs:
        print("No result JSONs found in results/.", file=sys.stderr)
        return 1
    md = render_compare(runs)
    (out_dir / "compare.md").write_text(md)
    print(md)
    return 0


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trapstreet-eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--mode",
            choices=("evidence", "pdf"),
            default="evidence",
            help="evidence: gold passages only · pdf: full 10-K text (slower, more realistic)",
        )
        p.add_argument("--limit", type=int, default=0, help="cap question count (0=all)")
        p.add_argument("--no-judge", action="store_true", help="disable LLM judge fallback")

    p_run = sub.add_parser("run", help="run a single agent")
    p_run.add_argument(
        "--agent",
        required=True,
        help="naive | claude | claude-haiku | gpt-4o | gpt-4o-mini | your-agent",
    )
    _add_common(p_run)
    p_run.set_defaults(func=cmd_run)

    p_cmp = sub.add_parser("compare", help="run multiple agents and produce a leaderboard")
    p_cmp.add_argument("--agents", required=True, help="comma-separated agent names")
    _add_common(p_cmp)
    p_cmp.set_defaults(func=cmd_compare)

    p_rep = sub.add_parser("report", help="re-render the leaderboard from existing results/")
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(cli())
