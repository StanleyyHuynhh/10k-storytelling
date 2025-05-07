import os
import json
import re
import argparse
from typing import Optional, Tuple

from generate_financial_summary import generate_financial_summary, call_ollama
from grade_narrative import grade_narrative

def strip_markdown(text: str) -> str:
    # remove **bold**, *italic*, and backticks
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*',    r'\1', text)
    return text.replace('`', '')

def create_narrative(
    cleaned_txt: str,
    pages: int = 3,
    summary_model: str = "llama3.2",
    grade_model: str = "gemma3:4b",
    output_initial: Optional[str] = None,
    output_refined: Optional[str] = None
) -> Tuple[str, str]:
    """
    1. Generates a data-rich financial summary from cleaned text.
    2. Grades that summary to get feedback and writes grade JSON.
    3. Refines the summary into a narrative using the feedback.
    Returns paths to initial_summary and refined_story.
    """
    # Use the cleaned file base directly
    base, _ = os.path.splitext(cleaned_txt)

    summary_txt = output_initial or f"{base}_financial_overview.txt"
    refined_txt = output_refined or f"{base}_narrative.txt"
    grade_json = f"{base}_overview_grade.json"

    # Step 1: generate financial summary
    print("▶ Generating financial summary...")
    generate_financial_summary(
        input_txt=cleaned_txt,
        output_txt=summary_txt,
        pages=pages,
        model=summary_model
    )

    # Step 2: grade the summary
    print("▶ Grading financial summary...")
    score, feedback = grade_narrative(
        narrative_path=summary_txt,
        model=grade_model
    )
    # Write grading JSON to file
    with open(grade_json, 'w', encoding='utf-8') as gf:
        json.dump({"score": score, "feedback": feedback}, gf, indent=2)
    print(f"✅ Grading results saved to: {grade_json}")

    # Build feedback text for the refinement prompt
    feedback_text = "\n".join(f"- {item}" for item in feedback)

    # Step 3: refine into narrative
    print("▶ Creating narrative from summary...")
    with open(summary_txt, 'r', encoding='utf-8') as f:
        summary_content = f.read().strip()

    refine_prompt = (
        "You are a skilled financial journalist tasked with transforming a factual financial summary into an engaging narrative report. "
        "Your goal is to convert bullet-point facts into a compelling story that maintains complete accuracy while being more readable and engaging.\n\n"
        
        "# INSTRUCTIONS\n"
        "1. Convert the bullet-point format into flowing paragraphs with a cohesive narrative structure\n"
        "2. Maintain ALL factual information - every number and data point must be preserved exactly\n"
        "3. Group related information into logical sections with clear headings\n"
        "4. Add appropriate transitions between sections and ideas\n"
        "5. Use a professional, authoritative tone suitable for investors and financial professionals\n"
        "6. Include a brief executive summary at the beginning highlighting key points\n"
        "7. Address all feedback points provided below\n\n"
        
        f"# FACTUAL SUMMARY\n{summary_content}\n\n"
        
        f"# FEEDBACK TO ADDRESS\n{feedback_text}\n\n"
        
        "# OUTPUT FORMAT\n"
        "Create a well-structured narrative with clear sections, engaging transitions, and a compelling flow. "
        "Use paragraph breaks appropriately. Include an executive summary followed by detailed sections that "
        "present the information in a logical order.\n\n"
        
        "BEGIN YOUR NARRATIVE REPORT:"
    )
    
    # raw LLM output (may contain **bold**, etc.)
    raw_narrative = call_ollama(refine_prompt, model=summary_model)
    
    # strip out any stray markdown before saving
    narrative = strip_markdown(raw_narrative)

    with open(refined_txt, 'w', encoding='utf-8') as f:
        f.write(narrative)

    print(f"✅ Refined narrative saved to: {refined_txt}")
    return summary_txt, refined_txt


def main():
    parser = argparse.ArgumentParser(
        description="Generate and refine a narrative from cleaned 10-K text."
    )
    parser.add_argument(
        "--cleaned", "-c", required=True,
        help="Path to cleaned 10-K text file"
    )
    parser.add_argument(
        "--pages", "-p", type=int, default=3,
        help="Approximate pages for the financial summary"
    )
    parser.add_argument(
        "--summary-model", default="llama3.2",
        help="Model for financial summary"
    )
    parser.add_argument(
        "--grade-model", default="gemma3:4b",
        help="Model for grading summary"
    )
    parser.add_argument(
        "--output-initial", "-o1", 
        help="Custom path for initial financial summary"
    )
    parser.add_argument(
        "--output-refined", "-o2",
        help="Custom path for refined narrative"
    )
    args = parser.parse_args()

    init, refined = create_narrative(
        cleaned_txt=args.cleaned,
        pages=args.pages,
        summary_model=args.summary_model,
        grade_model=args.grade_model,
        output_initial=args.output_initial,
        output_refined=args.output_refined
    )
    print(f"✅ Financial summary saved to: {init}")
    print(f"✅ Refined narrative saved to: {refined}")

if __name__ == '__main__':
    main()