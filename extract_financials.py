import os
import json
import argparse
import subprocess
import re
from typing import List, Dict, Any, Optional

def strip_markdown(text: str) -> str:
    # remove **bold** and *italic*
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    # remove any inline code ticks
    return text.replace('`', '')

def call_ollama(prompt: str, model: str = "gemma3:4b") -> str:
    cmd = ["ollama", "run", model]
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ollama call failed: {result.stderr}")
    return result.stdout.strip()


def extract_financial_buckets_from_summary(
    summary_text: str,
    model: str = "gemma3:4b"
) -> List[Dict[str, Any]]:
    """
    Use LLM to extract key financial line items; fallback to regex for capturing values with units.
    Returns values consistently in millions.
    """
    # 1) Try LLM extraction with improved prompt
    prompt = (
        "# Financial Data Extraction Task\n\n"
        "You are a financial analyst specializing in SEC filings and corporate financial statements. "
        "I need your expertise to extract precise financial data from the text below, which comes from "
        "a company's annual report (10-K filing).\n\n"
        
        "## Instructions\n"
        "1. Carefully analyze the financial summary to locate the following annual line items\n"
        "2. Extract the *exact numerical values* as they appear in the text\n"
        "3. Convert all values to millions of dollars for consistency\n"
        "4. Pay special attention to units (million vs. billion) and adjust accordingly\n"
        "5. For any value not explicitly mentioned, leave as 0.0\n"
        "6. If multiple years are mentioned, extract the most recent year's data only\n\n"
        
        "## Required Financial Data Points\n"
        "Extract these specific line items:\n"
        "- Products revenue\n"
        "- Services revenue\n"
        "- Total Revenue\n"
        "- Cost of Revenue\n"
        "- Gross Profit\n"
        "- Operating Expenses\n"
        "- Operating Income\n"
        "- Interest Expense\n"
        "- Interest Income\n"
        "- Other Income/Expense\n"
        "- Income Tax Expense\n"
        "- Net Income\n\n"
        
        "## Response Format\n"
        "Respond ONLY with a valid JSON array with this exact structure:\n"
        "[\n"
        "  {\"bucket\":\"Products\",\"value\":0.0},\n"
        "  {\"bucket\":\"Services\",\"value\":0.0},\n"
        "  {\"bucket\":\"Revenue\",\"value\":0.0},\n"
        "  {\"bucket\":\"Cost of Revenue\",\"value\":0.0},\n"
        "  {\"bucket\":\"Gross Profit\",\"value\":0.0},\n"
        "  {\"bucket\":\"Operating Expenses\",\"value\":0.0},\n"
        "  {\"bucket\":\"Operating Income\",\"value\":0.0},\n"
        "  {\"bucket\":\"Interest Expense\",\"value\":0.0},\n"
        "  {\"bucket\":\"Interest Income\",\"value\":0.0},\n"
        "  {\"bucket\":\"Other Income/Expense\",\"value\":0.0},\n"
        "  {\"bucket\":\"Taxes\",\"value\":0.0},\n"
        "  {\"bucket\":\"Net Income\",\"value\":0.0}\n"
        "]\n\n"
        
        "## Financial Summary Text\n"
        f"{summary_text}\n\n"
        
        "Remember: Return ONLY the JSON array with no additional commentary or explanation."
    )
    
    raw = call_ollama(prompt, model=model)   
    
    # Strip out any Markdown before parsing
    response = strip_markdown(raw)

    # Debug print
    print("🔍 LLM raw response:\n", response)

    # Parse JSON from LLM - improved parsing logic
    buckets: List[Dict[str, Any]] = []
    try:
        # Look for JSON array anywhere in the response
        start = response.find('[')
        end = response.rfind(']') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            buckets = json.loads(json_str)
            print(f"✅ Successfully parsed JSON from LLM response")
        else:
            print("⚠️ No JSON array found in LLM response")
    except Exception as e:
        print(f"⚠️ Failed to parse JSON: {e}")
        buckets = []

    # Validate extracted values
    valid_buckets = all(
        isinstance(item.get('value', 0), (int, float)) for item in buckets
    )
    
    # Enhanced fallback with better regex patterns
    if not buckets or not valid_buckets or all(item.get('value', 0) == 0 for item in buckets):
        print("⚠️ Using regex fallback extraction")
        buckets = []
        patterns = {
            "Products": [
                r"Products(?:\s+revenue)?[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Product\s+sales[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Services": [
                r"Services(?:\s+revenue)?[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Service\s+revenue[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Revenue": [
                r"(?:Total\s+)?Revenue[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Net\s+sales[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Cost of Revenue": [
                r"Cost\s+of\s+(?:Revenue|Sales)[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"COGS[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Gross Profit": [
                r"Gross\s+Profit[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Gross\s+Margin[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Operating Expenses": [
                r"Operating\s+Expenses[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"(?:Total\s+)?OPEX[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Operating Income": [
                r"Operating\s+Income[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Income\s+from\s+operations[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Operating\s+(?:profit|earnings)[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Interest Expense": [
                r"Interest\s+Expense[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Interest\s+expenses[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Interest Income": [
                r"Interest\s+Income[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Interest\s+earned[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Other Income/Expense": [
                r"Other\s+Income(?:/Expense)?[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Other\s+income\s+and\s+expense[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Taxes": [
                r"(?:Income\s+)?Tax(?:es)?(?:\s+Expense)?[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Provision\s+for\s+(?:income\s+)?taxes[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ],
            "Net Income": [
                r"Net\s+Income[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Net\s+Earnings[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?",
                r"Net\s+Profit[^0-9$]*\$?([\d,]+(?:\.\d+)?)(?:\s*(million|billion|m|b|M|B))?"
            ]
        }
        
        # Expanded unit detection
        unit_multiplier = {
            "million": 1.0, "m": 1.0, "M": 1.0,
            "billion": 1000.0, "b": 1000.0, "B": 1000.0
        }
        
        for bucket, pattern_list in patterns.items():
            val = 0.0
            for pattern in pattern_list:
                m = re.search(pattern, summary_text, flags=re.IGNORECASE)
                if m:
                    num_str = m.group(1).replace(',', '')
                    try:
                        val = float(num_str)
                        unit = (m.group(2) or "").lower()
                        val *= unit_multiplier.get(unit, 1.0)
                        print(f"📊 Found {bucket}: {val} million")
                        break  # Found a valid match, stop trying patterns
                    except ValueError:
                        continue
            
            buckets.append({"bucket": bucket, "value": val})

    # Validate results - check if Revenue = Products + Services
    revenue_idx = next((i for i, item in enumerate(buckets) if item["bucket"] == "Revenue"), -1)
    products_idx = next((i for i, item in enumerate(buckets) if item["bucket"] == "Products"), -1)
    services_idx = next((i for i, item in enumerate(buckets) if item["bucket"] == "Services"), -1)

    # If we have Revenue but no Products/Services, try to infer them from context
    if (revenue_idx != -1 and 
        (buckets[products_idx]["value"] == 0 or buckets[services_idx]["value"] == 0) and
        buckets[revenue_idx]["value"] > 0):
        
        # Try with another prompt specifically for product/service breakdown
        breakdown_prompt = (
            "As a financial analyst, analyze this 10-K summary to determine the breakdown of "
            "revenue between Products and Services. If exact figures aren't provided, estimate "
            "based on percentages or context clues. Format your response as a JSON array with "
            "ONLY these two values in millions of dollars:\n"
            "[{\"bucket\":\"Products\",\"value\":0.0}, {\"bucket\":\"Services\",\"value\":0.0}]\n\n"
            f"{summary_text}"
        )
        
        try:
            breakdown_raw = call_ollama(breakdown_prompt, model=model)
            breakdown_resp = strip_markdown(breakdown_raw)
            start = breakdown_resp.find('[')
            end = breakdown_resp.rfind(']') + 1
            if start >= 0 and end > start:
                breakdown_json = json.loads(breakdown_resp[start:end])
                for item in breakdown_json:
                    if item["bucket"] == "Products" and item["value"] > 0:
                        buckets[products_idx]["value"] = item["value"]
                    if item["bucket"] == "Services" and item["value"] > 0:
                        buckets[services_idx]["value"] = item["value"]
                print("✅ Enhanced Products/Services breakdown")
        except Exception as e:
            print(f"⚠️ Failed to parse product/service breakdown: {e}")
    
    # Final validation
    # Make sure revenue equals products + services if both are non-zero
    if (buckets[products_idx]["value"] > 0 and buckets[services_idx]["value"] > 0):
        sum_parts = buckets[products_idx]["value"] + buckets[services_idx]["value"]
        revenue_val = buckets[revenue_idx]["value"]
        
        # If there's a significant discrepancy, adjust
        if abs(sum_parts - revenue_val) > 0.01 * revenue_val and revenue_val > 0:
            # Adjust proportionally if both products and services have values
            if buckets[products_idx]["value"] > 0 and buckets[services_idx]["value"] > 0:
                ratio = revenue_val / sum_parts
                buckets[products_idx]["value"] *= ratio
                buckets[services_idx]["value"] *= ratio
                print(f"⚠️ Adjusted Products/Services to match Revenue (ratio: {ratio:.2f})")

    return buckets


def analyze_financials(
    summary_file: str,
    output_json: Optional[str] = None,
    model: str = "gemma3:4b"
) -> str:
    with open(summary_file, 'r', encoding='utf-8') as f:
        summary_text = f.read()

    buckets = extract_financial_buckets_from_summary(summary_text, model)

    out_path = output_json or os.path.splitext(summary_file)[0] + "_buckets.json"
    with open(out_path, 'w', encoding='utf-8') as fw:
        json.dump(buckets, fw, indent=2)

    return out_path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Extract financial buckets from 10-K summary for Sankey diagram visualization."
    )
    parser.add_argument("--input", "-i", required=True, help="Path to financial summary .txt file")
    parser.add_argument("--output","-o", help="Path to output buckets JSON file")
    parser.add_argument("--model","-m", default="gemma3:4b", help="Ollama model to use (default: gemma3:4b)")
    args = parser.parse_args()

    result = analyze_financials(
        summary_file=args.input,
        output_json=args.output,
        model=args.model
    )
    print(f"✅ Financial buckets extracted and saved to: {result}")
    print("\nExtracted financial data (in millions):")
    print("----------------------------------------")
    for b in json.load(open(result)):
        print(f"{b['bucket']}: ${b['value']:.2f}M")