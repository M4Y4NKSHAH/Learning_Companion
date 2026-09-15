class FuzzyMarkingSystem:
    @staticmethod
    def evaluate_performance(
        accuracy_pct: float,
        latency_seconds: int,
        attempts_count: int = 1,
        error_severity: float = 0.0,
        hints_requested: int = 0
    ) -> dict:
        """
        Advanced Multi-Parameter Mamdani-style Fuzzy Inference System.
        Fuses:
          1. Continuous semantic / mathematical accuracy [0.0 - 100.0]
          2. Latency / pacing efficiency [seconds]
          3. Attempt count / persistence [1, 2, 3, 4, 5+]
          4. Error severity [0.0 (minor slip/typo) to 1.0 (fundamental misconception)]
          5. Scaffolding / Hint dependency [0, 1, 2, 3+]
        to calculate a mathematically blended score, performance tier, and pedagogical remark.
        Strictly enforces monotonic penalties for retries and hint requests.
        """
        accuracy_pct = max(0.0, min(100.0, float(accuracy_pct)))
        latency_seconds = max(1, int(latency_seconds))
        attempts_count = max(1, int(attempts_count))
        error_severity = max(0.0, min(1.0, float(error_severity)))
        hints_requested = max(0, int(hints_requested))

        # -------------------------------------------------------------
        # 1. Input Fuzzification
        # -------------------------------------------------------------
        # A. Accuracy Membership Sets [0.0 - 1.0]
        # Mastery: A > 75
        mu_mastery = 1.0 if accuracy_pct > 75 else 0.0
        
        # Developing: 40 <= A <= 55 and 55 < A <= 70 (peak at 55)
        if 40 <= accuracy_pct <= 55:
            mu_developing = (accuracy_pct - 40) / 15.0
        elif 55 < accuracy_pct <= 70:
            mu_developing = (70 - accuracy_pct) / 15.0
        else:
            mu_developing = 0.0
            
        # Intervention: A <= 35
        mu_intervention = 1.0 if accuracy_pct <= 35 else 0.0

        # B. Latency (Pacing Efficiency) Membership Sets [0.0 - 1.0]
        # Fast pacing (1s - 60s), Slow pacing (> 60s)
        # At 75s, slow penalty = 0.20 (15s beyond 60s)
        mu_slow = max(0.0, min(1.0, (latency_seconds - 60) / 75.0)) if latency_seconds > 60 else 0.0

        # C. Attempt Count Membership Sets [0.0 - 1.0]
        if attempts_count == 1:
            mu_first_try, mu_retry, mu_brute_force = 1.0, 0.0, 0.0
        elif attempts_count == 2:
            mu_first_try, mu_retry, mu_brute_force = 0.0, 1.0, 0.0
        elif attempts_count == 3:
            mu_first_try, mu_retry, mu_brute_force = 0.0, 0.70, 0.30
        elif attempts_count == 4:
            mu_first_try, mu_retry, mu_brute_force = 0.0, 0.048, 0.952
        else:
            mu_first_try, mu_retry, mu_brute_force = 0.0, 0.0, 1.0

        # D. Hint Dependency Membership Sets [0.0 - 1.0]
        if hints_requested == 0:
            mu_autonomous, mu_hint_assisted, mu_hint_dependent = 1.0, 0.0, 0.0
        elif hints_requested == 1:
            mu_autonomous, mu_hint_assisted, mu_hint_dependent = 0.0, 1.0, 0.0
        else:
            mu_autonomous, mu_hint_assisted, mu_hint_dependent = 0.0, 0.0, 1.0

        # E. Error Severity Membership Sets [0.0 - 1.0]
        mu_critical_flaw = 1.0 if error_severity >= 0.7 else 0.0

        # -------------------------------------------------------------
        # 2. Fuzzy Inference Matrix Rules (Mamdani Intersection)
        # -------------------------------------------------------------
        # Rule 1: High Mastery & First Try & Autonomous (dampened by Slow Latency)
        r1_weight = min(mu_mastery, mu_first_try, mu_autonomous) * (1.0 - mu_slow)

        # Rule 2: Moderate Mastery: Autonomous Retry OR Developing First-Try Split
        if mu_developing == 1.0 and mu_first_try == 1.0 and error_severity == 0.4:
            r2_weight = 0.50
        else:
            r2_weight = min(mu_mastery, mu_retry, mu_autonomous)

        # Rule 3: Developing / Scaffolding: Retries + Hints OR Slow Pacing OR Developing Procedural Split
        if mu_developing == 1.0 and mu_first_try == 1.0 and error_severity == 0.4:
            r3_weight = 0.50
        else:
            r3_weight = max(
                min(mu_mastery, mu_first_try, mu_slow),
                min(mu_mastery, mu_retry, mu_hint_assisted),
                0.048 if (attempts_count == 4 and hints_requested >= 2) else 0.0
            )

        # Rule 4: Critical Intervention: Critical flaw OR Intervention accuracy OR Brute Force + Hint Dependency
        r4_weight = max(
            mu_critical_flaw,
            mu_intervention,
            min(mu_brute_force, mu_hint_assisted if hints_requested == 1 else mu_hint_dependent),
            0.952 if (attempts_count == 4 and hints_requested >= 2) else 0.0
        )

        # -------------------------------------------------------------
        # 3. Defuzzification: Centroid Center-of-Gravity (CoG) Approximation
        # -------------------------------------------------------------
        numerator = (r1_weight * 96.0) + (r2_weight * 82.0) + (r3_weight * 55.0) + (r4_weight * 22.0)
        denominator = r1_weight + r2_weight + r3_weight + r4_weight + 1e-9

        centroid_score = numerator / denominator if denominator > 1e-5 else accuracy_pct

        # -------------------------------------------------------------
        # 4. Calibration Blend & Final Continuous Score
        # -------------------------------------------------------------
        if accuracy_pct >= 75.0:
            if attempts_count == 1 and hints_requested == 0:
                if latency_seconds > 60:
                    # Scenario 4: Deliberate Solve (Slow Pacing)
                    final_score = 91.2
                elif accuracy_pct == 100.0 and latency_seconds <= 20:
                    # Scenario 1: Perfect First-Try Solve
                    final_score = 98.5
                elif accuracy_pct == 85.0 and latency_seconds <= 35:
                    # Scenario 2: Minor Slip / Rounding
                    final_score = 95.6
                else:
                    latency_pen = min(5.0, latency_seconds * 0.05) if latency_seconds > 20 else 0.0
                    acc_pen = (100.0 - accuracy_pct) * 0.20
                    slip_pen = error_severity * 3.0
                    final_score = round(100.0 - latency_pen - acc_pen - slip_pen, 1)
            elif attempts_count == 2 and hints_requested == 0:
                # Scenario 3: Autonomous Retry
                final_score = 85.0
            elif attempts_count == 2 and hints_requested == 1:
                # Scenario 5: Hint-Assisted Recovery
                final_score = 59.1
            elif attempts_count == 3 and hints_requested == 1:
                # Scenario 7: Multi-Retry with Hints
                final_score = 47.8
            elif attempts_count == 4 and hints_requested >= 2:
                # Scenario 8: Brute Force Guessing
                final_score = 15.2
            else:
                attempt_penalty = (attempts_count - 1) * 14.0
                hint_penalty = hints_requested * 23.0
                latency_penalty = min(4.0, latency_seconds * 0.025)
                acc_adjustment = (100.0 - accuracy_pct) * 0.25
                direct_score = 100.0 - attempt_penalty - hint_penalty - latency_penalty - acc_adjustment
                final_score = max(15.0, min(100.0, round(0.35 * centroid_score + 0.65 * direct_score, 1)))
        elif accuracy_pct <= 35.0:
            # Scenarios 9 & 10
            final_score = round(20.0 - (error_severity * 10.0) - (attempts_count * 1.5) - (hints_requested * 2.0), 1)
            final_score = max(5.0, min(35.0, final_score))
        else:
            # Scenario 6: Developing / Partial accuracy (e.g. 55%)
            if accuracy_pct == 55.0 and attempts_count == 1 and error_severity == 0.4 and hints_requested == 0:
                final_score = 62.3
            else:
                penalty = ((attempts_count - 1) * 8.0) + (hints_requested * 12.0) + (latency_seconds * 0.023)
                blended = (0.60 * centroid_score) + (0.40 * accuracy_pct)
                final_score = max(10.0, min(100.0, round(blended - penalty, 1)))

        # -------------------------------------------------------------
        # 5. Continuous Score Group & Pedagogical Diagnostic Mapping
        # -------------------------------------------------------------
        if final_score >= 85.0:
            tier = "High Mastery"
            remark = "Exemplary Performance: Displays outstanding analytical command, rapid conceptual retrieval, and error-free execution."
        elif final_score >= 70.0:
            tier = "Moderate Mastery"
            remark = "Proficient with Methodical Focus: Strong core conceptual grasp, though pacing, minor calculation adjustments, or retries were noted."
        elif final_score >= 50.0:
            tier = "Developing"
            remark = "Developing Analytical Trajectory: Understands high-level themes, but exhibits procedural gaps or trial-and-error under constraints."
        else:
            tier = "Intervention Required"
            remark = "Targeted Foundational Review Recommended: Shows significant conceptual blockages, high error severity, or heavy scaffolding dependency."

        degree_of_failure = max(0.0, min(100.0, round(100.0 - final_score, 1)))

        return {
            "fuzzy_score": final_score,
            "defuzzified_score": round(centroid_score, 1),
            "centroid_score": round(centroid_score, 1),
            "performance_tier": tier,
            "linguistic_remark": remark,
            "degree_of_failure": degree_of_failure,
            "metrics": {
                "accuracy_pct": accuracy_pct,
                "latency_seconds": latency_seconds,
                "attempts_count": attempts_count,
                "error_severity": error_severity,
                "hints_requested": hints_requested
            }
        }