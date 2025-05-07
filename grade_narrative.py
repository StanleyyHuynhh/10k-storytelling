import os
import argparse
import subprocess
import json
from typing import List, Tuple, Dict, Any, Optional

def call_ollama(prompt: str, model: str = "gemma3:4b") -> str:
    """
    Sends a prompt to a local Ollama model via CLI and returns the raw output as plain text.
    
    Args:
        prompt: The input text to send to the model
        model: The Ollama model identifier to use
        
    Returns:
        The raw text response from the model
        
    Raises:
        RuntimeError: If the Ollama call fails
    """
    cmd = ["ollama", "run", model]
    try:
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
    except Exception as e:
        raise RuntimeError(f"Error calling Ollama: {str(e)}")


def grade_narrative(
    narrative_path: str,
    model: str = "gemma3:4b",
    output_json: Optional[str] = None
) -> Tuple[int, List[str]]:
    """
    Evaluates a financial narrative for quality and provides a score and critical feedback.
    
    Args:
        narrative_path: Path to the narrative text file to evaluate
        model: The Ollama model to use for evaluation
        output_json: Optional path to save JSON evaluation results
        
    Returns:
        Tuple containing:
          - overall_score: int (1-10)
          - feedback: list of improvement points as strings
    """
    try:
        with open(narrative_path, "r", encoding="utf-8") as f:
            story = f.read().strip()
    except Exception as e:
        raise FileNotFoundError(f"Could not read narrative file: {str(e)}")

    # Enhanced grading prompt with more critical evaluation criteria
    prompt = (
        "You are a demanding financial editor at a top-tier business publication. "
        "Your task is to critically evaluate the following corporate financial narrative. "
        "Be strict, detailed, and focus on concrete improvements.\n\n"
        
        "Evaluation criteria:\n"
        "1. Factual accuracy and data representation (most important)\n"
        "2. Clarity and logical flow of financial information\n"
        "3. Balance between technical detail and accessibility\n"
        "4. Integration of financial metrics into a coherent story\n"
        "5. Appropriate context for business performance\n"
        "6. Professional tone suited for investors and analysts\n\n"
        
        f"NARRATIVE TO EVALUATE:\n{story}\n\n"
        
        "Instructions:\n"
        "- Assign a score from 1-10 (be critical, reserve 9-10 for truly exceptional work)\n"
        "- Provide 4-6 specific, actionable improvement points\n"
        "- Focus on substantive issues, not superficial ones\n"
        "- Be direct and specific in your criticism\n\n"
        
        "Output in exactly this format:\n"
        "SCORE: <number>\n"
        "FEEDBACK:\n"
        "- [specific improvement point]\n"
        "- [specific improvement point]\n"
        "..."
    )

    response = call_ollama(prompt, model=model)

    # Parse plain-text response with enhanced error handling
    lines = response.splitlines()
    score = 0
    feedback: List[str] = []
    
    in_feedback_section = False
    
    for line in lines:
        line = line.strip()
        if line.upper().startswith("SCORE:"):
            try:
                score_text = line.split(':', 1)[1].strip()
                # Handle potential text scores like "7/10"
                if '/' in score_text:
                    score = int(score_text.split('/')[0].strip())
                else:
                    score = int(score_text)
            except (ValueError, IndexError):
                pass
        elif line.upper() == "FEEDBACK:":
            in_feedback_section = True
        elif in_feedback_section and line.startswith("-"):
            point = line.lstrip('-').strip()
            if point:  # Only add non-empty feedback points
                feedback.append(point)
    
    # Ensure we have at least some feedback points
    if not feedback:
        # Try to extract any paragraph-like content as feedback
        for line in lines:
            if len(line.strip()) > 20 and not line.upper().startswith("SCORE:") and not line.upper() == "FEEDBACK:":
                feedback.append(line.strip())
                if len(feedback) >= 3:
                    break
    
    # Ensure score is within valid range
    score = max(1, min(10, score))
    
    # Make sure we have at least some feedback
    if not feedback:
        feedback = [
            "Narrative structure needs improvement for better flow",
            "Financial data should be presented more clearly with context",
            "Consider adding more comparative analysis between time periods"
        ]
    
    # Save results to JSON if requested
    if output_json:
        results = {
            "score": score,
            "feedback": feedback,
            "narrative_path": narrative_path,
            "model_used": model
        }
        try:
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save results to JSON: {str(e)}")
    
    return score, feedback


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Critically evaluate a financial narrative and provide actionable feedback."
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to the narrative text file to evaluate"
    )
    parser.add_argument(
        "--model", "-m", default="gemma3:4b",
        help="Ollama model to use for evaluation (default: gemma3:4b)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Optional path to save evaluation results as JSON"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print detailed output"
    )
    args = parser.parse_args()

    try:
        score, feedback = grade_narrative(args.input, args.model, args.output)
        
        print(f"Evaluation Score: {score}/10")
        print("\nFeedback Points:")
        for i, point in enumerate(feedback, 1):
            print(f" {i}. {point}")
            
        if args.output and args.verbose:
            print(f"\nDetailed results saved to: {args.output}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)