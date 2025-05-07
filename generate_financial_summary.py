import os
import argparse
import subprocess
from typing import Optional


def call_ollama(prompt: str, model: str = "llama3.2") -> str:
    """
    Sends the given prompt to a local Ollama model via CLI and returns the output.
    """
    cmd = ["ollama", "run", model]
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ollama call failed: {result.stderr}")
    return result.stdout.strip()


def generate_financial_summary(
    input_txt: str,
    output_txt: Optional[str] = None,
    pages: int = 5,
    model: str = "llama3.2"
) -> str:
    """
    Reads cleaned 10-K text, builds a data-rich financial analysis prompt,
    invokes Llama3.2 via Ollama, and writes the summary.
    Returns the path to the saved summary.
    """
    # Log start
    print("Generating financial summary...", flush=True)

    # Load cleaned text
    with open(input_txt, 'r', encoding='utf-8') as f:
        cleaned_text = f.read().strip()

    # Construct financial-analyst prompt
    prompt = (
    "You are an expert financial analyst with extensive experience extracting key information from SEC filings. Your task is to create a comprehensive, fact-based business summary from the provided 10-K text using clear bullet points. Focus on extracting all available factual information, even if the document contains limited financial details.\n\n"
    
    "# INSTRUCTIONS\n"
    "1. Create a detailed business summary using ONLY verifiable facts from the 10-K\n"
    "2. Format as organized bullet points with clear section headers\n"
    "3. Extract ALL available numerical data, no matter how limited\n"
    "4. Include year-over-year comparisons whenever provided\n"
    "5. Do NOT include subjective analysis or forward-looking statements\n"
    "6. Be thorough but concise - focus on the most significant facts\n"
    "7. If specific sections lack detail, include what's available and maintain the structure\n"
    "8. For missing data points, do not make assumptions or estimates\n\n"

    "# OUTPUT FORMAT\n"
    "## COMPANY OVERVIEW\n"
    "• [Company legal name] is a [description of business from 10-K]\n"
    "• Ticker symbol: [symbol], listed on [exchange]\n"
    "• Headquarters: [location]\n"
    "• Industry: [industry classification]\n"
    "• [Other key facts about business model, formation, etc.]\n\n"

    "## FINANCIAL HIGHLIGHTS (FY[YEAR])\n"
    "• Revenue: [amount if available], [change from previous year if available]\n"
    "• Net Income/Loss: [amount if available], [change from previous year if available]\n"
    "• [Include any other available financial metrics]\n"
    "• Market capitalization: [amount if available]\n"
    "• Outstanding shares: [number if available]\n\n"

    "## BUSINESS SEGMENTS\n"
    "• [List and briefly describe each business segment mentioned]\n"
    "• [Include segment revenue/profits if available]\n\n"

    "## KEY DEVELOPMENTS & GROWTH DRIVERS\n"
    "• [List significant business developments mentioned in the filing]\n"
    "• [Include any factors cited as driving growth or performance]\n\n"

    "## RISK FACTORS\n"
    "• [List key risk factors mentioned in the filing]\n"
    "• [Group similar risks if appropriate]\n\n"

    "## GOVERNANCE & COMPLIANCE\n"
    "• [Include relevant information about corporate governance]\n"
    "• [Note any significant compliance or regulatory matters]\n\n"

    "## ADDITIONAL NOTABLE FACTS\n"
    "• [Include any other significant factual information from the filing]\n\n"

    "CLEANED 10-K TEXT:\n\n"
    f"{cleaned_text}\n\n"
    "END."
)



    # Generate summary
    summary = call_ollama(prompt, model=model)

    # Save output
    out_path = output_txt or os.path.splitext(input_txt)[0] + "_summary.txt"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(summary)

    # Log completion
    print(f"Summary saved to: {out_path}", flush=True)
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate a data-rich financial summary from cleaned 10-K text using Llama3.2 via Ollama"
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to cleaned text file (e.g., cleaned_10k.txt)"
    )
    parser.add_argument(
        "--pages", "-p", type=int, default=5,
        help="Approximate overview length in pages (default: 5)"
    )
    parser.add_argument(
        "--model", "-m", default="llama3.2",
        help="Ollama model to use (default: llama3.2)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Path to save the summary (default: <input>_summary.txt)"
    )
    args = parser.parse_args()

    generate_financial_summary(
        input_txt=args.input,
        output_txt=args.output,
        pages=args.pages,
        model=args.model
    )

if __name__ == '__main__':
    main()
