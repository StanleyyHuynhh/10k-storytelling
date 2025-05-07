import os
import json
import argparse
from typing import Optional

from preprocess_10k import preprocess_10k
from generate_financial_summary import generate_financial_summary
from grade_narrative import grade_narrative
from extract_financials import analyze_financials
from visualize_sankey import plot_sankey
from create_story import create_narrative


def main():
    parser = argparse.ArgumentParser(
        description="Run the full 10-K pipeline: preprocess, summary, refine, and visualize."
    )
    parser.add_argument(
        "--input-pdf", "-i", required=True,
        help="Path to raw 10-K PDF"
    )
    parser.add_argument(
        "--pages", "-p", type=int, default=3,
        help="Approximate pages for initial summary (default: 3)"
    )
    parser.add_argument(
        "--story-model", default="llama3.2",
        help="Ollama model for summarization and storytelling"
    )
    parser.add_argument(
        "--grade-model", default="gemma3:4b",
        help="Ollama model for grading narratives"
    )
    args = parser.parse_args()

    base, _ = os.path.splitext(args.input_pdf)
    cleaned_txt     = f"{base}_cleaned.txt"
    summary_txt     = f"{base}_financial_overview.txt"
    grade_json      = f"{base}_overview_grade.json"
    narrative_txt   = f"{base}_narrative.txt"
    buckets_json    = f"{base}_financials.json"
    sankey_html     = f"{base}_sankey.html"

    # Step 1: Preprocessing
    print("Step 1/5: Preprocessing 10-K PDF...", flush=True)
    preprocess_10k(
        input_pdf=args.input_pdf,
        output_txt=cleaned_txt
    )
    print("-> Preprocessing complete.", flush=True)

    # Step 2: Generate financial summary
    print("Step 2/5: Generating financial summary...", flush=True)
    generate_financial_summary(
        input_txt=cleaned_txt,
        output_txt=summary_txt,
        pages=args.pages,
        model=args.story_model
    )
    print("-> Financial summary complete.", flush=True)

    # Step 3: Grade the financial overview
    print("Step 3/5: Grading financial overview...", flush=True)
    score, feedback = grade_narrative(
        narrative_path=summary_txt,
        model=args.grade_model
    )
    # Save grading output
    with open(grade_json, 'w', encoding='utf-8') as f:
        json.dump({"score": score, "feedback": feedback}, f, indent=2)
    print("-> Grading complete.", flush=True)

    # Step 4: Create narrative from summary
    print("Step 4/5: Creating narrative based on feedback...", flush=True)
    _, narrative_out = create_narrative(
        cleaned_txt=cleaned_txt,
        pages=args.pages,
        summary_model=args.story_model,
        grade_model=args.grade_model,
        output_initial=summary_txt,
        output_refined=narrative_txt
    )
    print("-> Narrative creation complete.", flush=True)

    # Step 5: Extract and visualize financial buckets
    print("Step 5/5: Extracting financial buckets and generating Sankey...", flush=True)
    analyze_financials(
        summary_file=cleaned_txt,
        output_json=buckets_json,
        model=args.grade_model
    )
    print("-> Buckets extraction complete.", flush=True)
    plot_sankey(
        json_path=buckets_json,
        output_html=sankey_html
    )
    print("-> Sankey chart complete.", flush=True)

    # Summary of outputs
    print("[Done] Pipeline complete!", flush=True)
    print(f"  Cleaned text:          {cleaned_txt}", flush=True)
    print(f"  Financial overview:    {summary_txt}", flush=True)
    print(f"  Grade (score):         {score}/10", flush=True)
    print(f"  Narrative:             {narrative_out}", flush=True)
    print(f"  Financial buckets:     {buckets_json}", flush=True)
    print(f"  Sankey diagram:        {sankey_html}", flush=True)


if __name__ == '__main__':
    main()
