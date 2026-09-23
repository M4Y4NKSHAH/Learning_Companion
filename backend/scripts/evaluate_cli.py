import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
from fuzzy_engine import FuzzyMarkingSystem

def print_result(res):
    print("\n" + "-" * 60)
    print("MAMDANI FUZZY INFERENCE EVALUATION RESULT")
    print("-" * 60)
    print(f"  * Fuzzy Score        : {res['fuzzy_score']}%")
    print(f"  * Performance Tier   : {res['performance_tier']}")
    print(f"  * Degree of Failure  : {res['degree_of_failure']}%")
    print(f"  * Linguistic Verdict : {res['linguistic_remark']}")
    print("-" * 60)
    print("  Inputs Evaluated:")
    for k, v in res["metrics"].items():
        print(f"    - {k}: {v}")
    print("-" * 60 + "\n")

def interactive_eval():
    print("=" * 60)
    print("INTERACTIVE MAMDANI FUZZY ENGINE EVALUATOR")
    print("=" * 60)
    print("Type your custom student parameters below (or press Ctrl+C to exit):\n")

    while True:
        try:
            acc_str = input("1. Accuracy Percentage [0 - 100] (e.g. 85): ").strip()
            if not acc_str: continue
            acc = float(acc_str)

            lat_str = input("2. Response Latency in seconds (e.g. 25): ").strip()
            lat = int(lat_str) if lat_str else 25

            att_str = input("3. Attempts Count [1, 2, 3, 4+] (default 1): ").strip()
            att = int(att_str) if att_str else 1

            sev_str = input("4. Error Severity [0.0 (typo/slip) to 1.0 (critical flaw)] (default 0.0): ").strip()
            sev = float(sev_str) if sev_str else 0.0

            hnt_str = input("5. Hints Requested [0, 1, 2+] (default 0): ").strip()
            hnt = int(hnt_str) if hnt_str else 0

            res = FuzzyMarkingSystem.evaluate_performance(
                accuracy_pct=acc,
                latency_seconds=lat,
                attempts_count=att,
                error_severity=sev,
                hints_requested=hnt
            )
            print_result(res)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting evaluator. Happy testing!")
            break
        except Exception as e:
            print(f"Error: {e}. Please enter valid numbers.\n")

if __name__ == "__main__":
    interactive_eval()
