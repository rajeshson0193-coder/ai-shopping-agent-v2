"""Command-line entry: python -m shopping_agent "best laptop under $1000" """

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from shopping_agent.parse import parse_budget_arg
from shopping_agent.pipeline import run_research


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Research shopping options. Profiles: laptop, headphones. Python pipeline only. "
            "In PowerShell prefer --budget 1000, or single quotes around $ amounts."
        )
    )
    parser.add_argument("request", nargs="?", default="best laptop under $1000")
    parser.add_argument(
        "--budget",
        default=None,
        help="USD budget override. Use this in PowerShell so $1000 is not stripped.",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-results-per-source", type=int, default=10)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also call eBay/SerpApi when API keys are present in the environment.",
    )
    parser.add_argument(
        "--skip-serpapi",
        action="store_true",
        help="Do not call SerpApi (saves monthly credits; eBay-only live discovery).",
    )
    parser.add_argument(
        "--serpapi-max-calls",
        type=int,
        default=None,
        help=(
            "Max SerpApi HTTP requests for this run (default 5 via SERPAPI_MAX_CALLS). "
            "eBay remains the primary live source."
        ),
    )
    parser.add_argument(
        "--no-fixtures",
        action="store_true",
        help="Do not load local listing fixtures (requires --live and keys).",
    )
    parser.add_argument(
        "--output",
        default="output/latest_report.json",
        help="JSON report path (parent folders are created).",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Also ask local Ollama for overview + per-pick narration (soft-skips if offline).",
    )
    parser.add_argument(
        "--ollama-model",
        default="qwen3:4b-instruct",
        help="Ollama model tag used with --explain (default qwen3:4b-instruct).",
    )
    args = parser.parse_args(argv)

    budget: Decimal | None = None
    if args.budget is not None:
        try:
            budget = parse_budget_arg(args.budget)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    try:
        result = run_research(
            args.request,
            limit=args.limit,
            max_results_per_source=args.max_results_per_source,
            timeout=args.timeout,
            use_fixtures=not args.no_fixtures,
            live=args.live,
            budget=budget,
            skip_serpapi=args.skip_serpapi,
            serpapi_max_calls=args.serpapi_max_calls,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()

    explanation = None
    if args.explain:
        from shopping_agent.explain import explain_report

        explanation = explain_report(payload, model=args.ollama_model)
        payload["explanation"] = explanation.to_dict()

    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Request: {result.request.raw_text}")
    print(f"Category: {result.request.category} | Budget: ${result.request.budget} {result.request.currency}")
    print(f"Stages: {' -> '.join(result.stages_run)}")
    print(f"Recommendations: {len(result.recommendations)} | Excluded: {len(result.excluded)}")
    if result.source_errors:
        print(f"Source errors: {result.source_errors}")
    print()
    if explanation and explanation.available and explanation.overview:
        print("Overview:")
        print(explanation.overview)
        print()
    elif explanation and explanation.error:
        print(explanation.error)
        print()
    explain_by_rank = {
        int(pick["rank"]): pick.get("explanation")
        for pick in (explanation.pick_explanations if explanation else [])
        if isinstance(pick, dict) and pick.get("rank") is not None
    }
    for rank, item in enumerate(result.recommendations, start=1):
        price = item.candidate.listed_price
        flag = " [provisional]" if item.provisional else ""
        print(
            f"{item.candidate.model} | ${price} | score {item.score} | "
            f"{item.candidate.source} | {item.candidate.condition}{flag}"
        )
        print(f"  {item.candidate.product_url}")
        for reason in item.reasons[:4]:
            print(f"  - {reason}")
        narrated = explain_by_rank.get(rank)
        if isinstance(narrated, str) and narrated.strip():
            print(f"  explain: {narrated}")
        print()
    if not result.recommendations:
        print("No eligible recommendations. Check excluded reasons in the JSON report.")
        print()
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
