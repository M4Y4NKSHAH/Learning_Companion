import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fuzzy_engine import FuzzyMarkingSystem

def test_fuzzy_suite():
    print("=" * 70)
    print("MULTI-PARAMETER MAMDANI FUZZY SYSTEM COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. MATHEMATICS TEST BENCHMARKS
    # -------------------------------------------------------------
    print("\n[ SECTION 1: MATHEMATICS BENCHMARKS ]")
    
    math_cases = [
        {
            "id": "M1_PERFECT_SOLVE",
            "desc": "Calculates Net Force F=m*a (8*4=32 N) on Attempt 1 in 20s",
            "acc": 100.0, "latency": 20, "attempts": 1, "severity": 0.0, "hints": 0,
            "expected_tier": "High Mastery", "min_score": 90.0
        },
        {
            "id": "M2_MINOR_ROUNDING_SLIP",
            "desc": "Numerical approximation/rounding slip (e.g. 31.8 vs 32), Attempt 1, 35s",
            "acc": 85.0, "latency": 35, "attempts": 1, "severity": 0.1, "hints": 0,
            "expected_tier": "High Mastery", "min_score": 75.0
        },
        {
            "id": "M3_SIGN_PROCEDURAL_RETRY",
            "desc": "Algebraic sign inversion on Attempt 1, fixed on Attempt 2 in 60s with 1 hint",
            "acc": 100.0, "latency": 60, "attempts": 2, "severity": 0.3, "hints": 1,
            "expected_tier": "Developing", "min_score": 55.0, "max_score": 60.0
        },
        {
            "id": "M4_CRITICAL_FORMULA_FLAW",
            "desc": "Divided instead of multiplied (F = 8/4 = 2 N), Severity 0.9, 2 attempts, 75s",
            "acc": 0.0, "latency": 75, "attempts": 2, "severity": 0.9, "hints": 0,
            "expected_tier": "Intervention Required", "max_score": 35.0
        },
        {
            "id": "M5_BRUTE_FORCE_RECOVERY",
            "desc": "Trial and error recovery on Attempt 4 after 110s and 2 hints",
            "acc": 100.0, "latency": 110, "attempts": 4, "severity": 0.2, "hints": 2,
            "expected_tier": "Intervention Required", "max_score": 45.0
        }
    ]

    for c in math_cases:
        res = FuzzyMarkingSystem.evaluate_performance(
            accuracy_pct=c["acc"],
            latency_seconds=c["latency"],
            attempts_count=c["attempts"],
            error_severity=c["severity"],
            hints_requested=c["hints"]
        )
        print(f"\n* Case {c['id']}: {c['desc']}")
        print(f"  Inputs   : Acc={c['acc']}%, Lat={c['latency']}s, Att={c['attempts']}, Sev={c['severity']}, Hints={c['hints']}")
        print(f"  Output   : Fuzzy Score = {res['fuzzy_score']}% | Tier = {res['performance_tier']} | DoF = {res['degree_of_failure']}%")
        print(f"  Verdict  : {res['linguistic_remark']}")
        
        if "min_score" in c:
            assert res["fuzzy_score"] >= c["min_score"], f"Score {res['fuzzy_score']} below min {c['min_score']}"
        if "max_score" in c:
            assert res["fuzzy_score"] <= c["max_score"], f"Score {res['fuzzy_score']} above max {c['max_score']}"

    # -------------------------------------------------------------
    # 2. OBJECTIVE / SHORT-ANSWER BENCHMARKS
    # -------------------------------------------------------------
    print("\n\n[ SECTION 2: OBJECTIVE / FACTUAL RECALL BENCHMARKS ]")

    objective_cases = [
        {
            "id": "O1_RAPID_FACTUAL_RECALL",
            "desc": "Identifies friction direction ('south') instantly on Attempt 1 in 8s",
            "acc": 100.0, "latency": 8, "attempts": 1, "severity": 0.0, "hints": 0,
            "expected_tier": "High Mastery", "min_score": 95.0
        },
        {
            "id": "O2_SPELLING_TYPO",
            "desc": "Spelling typo ('mitochondria' -> 'mitochondira') with Partial Credit 90%, 15s",
            "acc": 90.0, "latency": 15, "attempts": 1, "severity": 0.1, "hints": 0,
            "expected_tier": "High Mastery", "min_score": 80.0
        },
        {
            "id": "O3_PLAUSIBLE_DISTRACTOR",
            "desc": "Selected closely related biological distractor ('chloroplast'), Severity 0.5, 30s",
            "acc": 0.0, "latency": 30, "attempts": 1, "severity": 0.5, "hints": 0,
            "expected_tier": "Intervention Required", "max_score": 40.0
        },
        {
            "id": "O4_COMPLETE_CATEGORY_ERROR",
            "desc": "Selected completely irrelevant term ('neutron' for cell energy), Severity 1.0, 50s",
            "acc": 0.0, "latency": 50, "attempts": 2, "severity": 1.0, "hints": 1,
            "expected_tier": "Intervention Required", "max_score": 25.0
        },
        {
            "id": "O5_ELIMINATION_GUESS",
            "desc": "Guessed correct term on Attempt 3 after exhausting other options, 65s",
            "acc": 100.0, "latency": 65, "attempts": 3, "severity": 0.0, "hints": 1,
            "expected_tier": "Developing", "max_score": 85.0
        }
    ]

    for c in objective_cases:
        res = FuzzyMarkingSystem.evaluate_performance(
            accuracy_pct=c["acc"],
            latency_seconds=c["latency"],
            attempts_count=c["attempts"],
            error_severity=c["severity"],
            hints_requested=c["hints"]
        )
        print(f"\n* Case {c['id']}: {c['desc']}")
        print(f"  Inputs   : Acc={c['acc']}%, Lat={c['latency']}s, Att={c['attempts']}, Sev={c['severity']}, Hints={c['hints']}")
        print(f"  Output   : Fuzzy Score = {res['fuzzy_score']}% | Tier = {res['performance_tier']} | DoF = {res['degree_of_failure']}%")
        print(f"  Verdict  : {res['linguistic_remark']}")

        if "min_score" in c:
            assert res["fuzzy_score"] >= c["min_score"], f"Score {res['fuzzy_score']} below min {c['min_score']}"
        if "max_score" in c:
            assert res["fuzzy_score"] <= c["max_score"], f"Score {res['fuzzy_score']} above max {c['max_score']}"

    # -------------------------------------------------------------
    # 3. RELATIVE ATTEMPTS & HINTS COMPARISON BENCHMARKS
    # -------------------------------------------------------------
    print("\n\n[ SECTION 3: MONOTONIC ATTEMPT & HINT PENALTY BENCHMARKS ]")

    # Test 1: Student 1 (2 attempts, 0 hints -> 80-85%) vs Student 2 (2 attempts, 1 hint -> 55-60%)
    s1 = FuzzyMarkingSystem.evaluate_performance(100.0, 45, attempts_count=2, error_severity=0.0, hints_requested=0)
    s2 = FuzzyMarkingSystem.evaluate_performance(100.0, 45, attempts_count=2, error_severity=0.0, hints_requested=1)
    print(f"* 2 Attempts (0 Hints) = {s1['fuzzy_score']}% vs 2 Attempts (1 Hint) = {s2['fuzzy_score']}%")
    assert 80.0 <= s1["fuzzy_score"] <= 85.0, f"2 Attempts 0 hints score {s1['fuzzy_score']} must be in [80.0, 85.0]"
    assert 55.0 <= s2["fuzzy_score"] <= 60.0, f"2 Attempts 1 hint score {s2['fuzzy_score']} must be in [55.0, 60.0]"
    assert s1["fuzzy_score"] > s2["fuzzy_score"], "Student without hints must score higher than student with hints!"

    # Test 2: Attempt 1 > Attempt 2 > Attempt 3 > Attempt 4 > Attempt 5 (all 0 hints)
    prev_score = 101.0
    for att in range(1, 6):
        res = FuzzyMarkingSystem.evaluate_performance(100.0, 45, attempts_count=att, error_severity=0.0, hints_requested=0)
        print(f"* Attempt {att} (0 Hints): {res['fuzzy_score']}% [{res['performance_tier']}]")
        assert res["fuzzy_score"] < prev_score, f"Attempt {att} score {res['fuzzy_score']} is not strictly lower than {prev_score}"
        prev_score = res["fuzzy_score"]

    # Test 3: 4 Attempts + 1 Hint drops into Intervention Required (< 50%)
    res_4att_hint = FuzzyMarkingSystem.evaluate_performance(100.0, 45, attempts_count=4, error_severity=0.0, hints_requested=1)
    print(f"* 4 Attempts + 1 Hint: {res_4att_hint['fuzzy_score']}% [{res_4att_hint['performance_tier']}]")
    assert res_4att_hint["fuzzy_score"] < 50.0, "4 Attempts + 1 Hint should drop below 50%"

    print("\n" + "=" * 70)
    print("SUCCESS: ALL BENCHMARKS & MONOTONIC SCORING TESTS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    test_fuzzy_suite()
