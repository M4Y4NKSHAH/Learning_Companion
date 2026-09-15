import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from fuzzy_engine import FuzzyMarkingSystem

scenarios = [
    {
        "id": 1,
        "name": "Perfect First-Try Solve",
        "inputs": {"accuracy_pct": 100.0, "latency_seconds": 15, "attempts_count": 1, "error_severity": 0.0, "hints_requested": 0},
        "exp_centroid": 96.0,
        "exp_final": 98.5,
        "exp_tier": "High Mastery"
    },
    {
        "id": 2,
        "name": "Minor Slip / Rounding",
        "inputs": {"accuracy_pct": 85.0, "latency_seconds": 30, "attempts_count": 1, "error_severity": 0.1, "hints_requested": 0},
        "exp_centroid": 96.0,
        "exp_final": 95.6,
        "exp_tier": "High Mastery"
    },
    {
        "id": 3,
        "name": "Autonomous Retry (Try 2, No Hints)",
        "inputs": {"accuracy_pct": 100.0, "latency_seconds": 45, "attempts_count": 2, "error_severity": 0.0, "hints_requested": 0},
        "exp_centroid": 82.0,
        "exp_final": 85.0,
        "exp_tier": "High Mastery"
    },
    {
        "id": 4,
        "name": "Deliberate Solve (Slow Pacing)",
        "inputs": {"accuracy_pct": 90.0, "latency_seconds": 75, "attempts_count": 1, "error_severity": 0.1, "hints_requested": 0},
        "exp_centroid": 87.8,
        "exp_final": 91.2,
        "exp_tier": "High Mastery"
    },
    {
        "id": 5,
        "name": "Hint-Assisted Recovery (1 Hint)",
        "inputs": {"accuracy_pct": 100.0, "latency_seconds": 60, "attempts_count": 2, "error_severity": 0.2, "hints_requested": 1},
        "exp_centroid": 55.0,
        "exp_final": 59.1,
        "exp_tier": "Developing"
    },
    {
        "id": 6,
        "name": "Developing / Partial Knowledge",
        "inputs": {"accuracy_pct": 55.0, "latency_seconds": 35, "attempts_count": 1, "error_severity": 0.4, "hints_requested": 0},
        "exp_centroid": 68.5,
        "exp_final": 62.3,
        "exp_tier": "Developing"
    },
    {
        "id": 7,
        "name": "Multi-Retry with Hints (Try 3, 1 Hint)",
        "inputs": {"accuracy_pct": 100.0, "latency_seconds": 65, "attempts_count": 3, "error_severity": 0.0, "hints_requested": 1},
        "exp_centroid": 45.1,
        "exp_final": 47.8,
        "exp_tier": "Intervention Required"
    },
    {
        "id": 8,
        "name": "Brute Force Guessing (Try 4-5)",
        "inputs": {"accuracy_pct": 100.0, "latency_seconds": 110, "attempts_count": 4, "error_severity": 0.2, "hints_requested": 2},
        "exp_centroid": 23.6,
        "exp_final": 15.2,
        "exp_tier": "Intervention Required"
    },
    {
        "id": 9,
        "name": "Critical Conceptual Misconception",
        "inputs": {"accuracy_pct": 0.0, "latency_seconds": 75, "attempts_count": 2, "error_severity": 0.9, "hints_requested": 0},
        "exp_centroid": 22.0,
        "exp_final": 8.0,
        "exp_tier": "Intervention Required"
    },
    {
        "id": 10,
        "name": "Total Category Error + Dependent",
        "inputs": {"accuracy_pct": 0.0, "latency_seconds": 50, "attempts_count": 2, "error_severity": 1.0, "hints_requested": 1},
        "exp_centroid": 22.0,
        "exp_final": 5.0,
        "exp_tier": "Intervention Required"
    }
]

def run_tests():
    print("=" * 80)
    print("TESTING 10 TABLE SCENARIOS AGAINST FUZZY INFERENCE ENGINE")
    print("=" * 80)

    all_passed = True
    for s in scenarios:
        res = FuzzyMarkingSystem.evaluate_performance(**s["inputs"])
        act_centroid = res.get("defuzzified_score", res.get("centroid_score"))
        act_final = res["fuzzy_score"]
        act_tier = res["performance_tier"]

        diff_centroid = abs(act_centroid - s["exp_centroid"])
        diff_final = abs(act_final - s["exp_final"])
        tier_match = act_tier == s["exp_tier"]

        passed = (diff_centroid < 1.5) and (diff_final < 1.5) and tier_match
        if not passed:
            all_passed = False

        status = "MATCH" if passed else "DIFF DETECTED"
        print(f"\nScenario {s['id']}: {s['name']} -> [{status}]")
        print(f"  Inputs: {s['inputs']}")
        print(f"  Centroid Defuzzified: Expected={s['exp_centroid']} | Actual={act_centroid} (Diff: {diff_centroid:.2f})")
        print(f"  Final Calibrated:     Expected={s['exp_final']} | Actual={act_final} (Diff: {diff_final:.2f})")
        print(f"  Performance Tier:     Expected={s['exp_tier']} | Actual={act_tier} (Match: {tier_match})")

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL 10 SCENARIOS MATCHED EXPECTED VALUES!")
    else:
        print("SOME SCENARIOS DIFFERED. INSPECT DETAILS ABOVE.")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
