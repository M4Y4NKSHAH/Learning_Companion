import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_BASE = 'http://127.0.0.1:8000'

def run_test():
    print("=" * 70)
    print("TESTING TUTOR HINT & SOLUTION ROUTING ACROSS SUBJECTS")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. BIOLOGY CLASS 10 TEST
    # -------------------------------------------------------------
    print("\n--- 1. Testing Biology (Class 10) ---")
    req = urllib.request.Request(
        f"{API_BASE}/api/tutor/load-theory",
        data=json.dumps({"current_subject": "Biology", "current_tier": "Class 10"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req)
    theory = json.loads(resp.read().decode("utf-8"))
    b_quiz = theory["quizzes"][0]
    print(f"Loaded Question: {b_quiz['text'][:60]}...")

    # Biology Hint
    hint_req = urllib.request.Request(
        f"{API_BASE}/api/tutor/chat",
        data=json.dumps({
            "message": f"Topic/Question: {b_quiz['concept']} ({b_quiz['text']}) | Student Inquiry: Can you give me a hint for this question?",
            "time_taken": 15,
            "consecutive_errors": 0,
            "current_tier": "Class 10",
            "current_subject": "Biology",
            "history": [],
            "current_question": b_quiz,
            "inquiry_type": "hint"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    b_hint = json.loads(urllib.request.urlopen(hint_req).read().decode("utf-8"))
    print(f"Hint Node: {b_hint['active_node']} | Depth: {b_hint['depth_level']}")
    print(f"Hint Text:\n{b_hint['response']}")
    assert "50 Newtons" not in b_hint['response'], "FAILURE: 50 Newtons found in Biology hint!"
    assert b_hint['active_node'] == "Socratic Hint Node", f"FAILURE: Expected Socratic Hint Node, got {b_hint['active_node']}"

    # Biology Solution
    sol_req = urllib.request.Request(
        f"{API_BASE}/api/tutor/chat",
        data=json.dumps({
            "message": f"Topic/Question: {b_quiz['concept']} ({b_quiz['text']}) | Student Inquiry: give me the answer please and show full solution",
            "time_taken": 15,
            "consecutive_errors": 0,
            "current_tier": "Class 10",
            "current_subject": "Biology",
            "history": [],
            "current_question": b_quiz,
            "inquiry_type": "solution"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    b_sol = json.loads(urllib.request.urlopen(sol_req).read().decode("utf-8"))
    print(f"\nSolution Node: {b_sol['active_node']} | Depth: {b_sol['depth_level']}")
    print(f"Solution Text:\n{b_sol['response']}")
    assert "50 Newtons" not in b_sol['response'], "FAILURE: 50 Newtons found in Biology solution!"
    assert "Mitochondria" in b_sol['response'], "FAILURE: Mitochondria not in Biology solution!"
    assert b_sol['active_node'] == "Direct Explainer Node", f"FAILURE: Expected Direct Explainer Node, got {b_sol['active_node']}"

    # -------------------------------------------------------------
    # 2. MATHEMATICS CLASS 10 TEST
    # -------------------------------------------------------------
    print("\n--- 2. Testing Mathematics (Class 10) ---")
    req_m = urllib.request.Request(
        f"{API_BASE}/api/tutor/load-theory",
        data=json.dumps({"current_subject": "Mathematics", "current_tier": "Class 10"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    theory_m = json.loads(urllib.request.urlopen(req_m).read().decode("utf-8"))
    m_quiz = theory_m["quizzes"][0]
    print(f"Loaded Question: {m_quiz['text']}")

    # Math Hint
    m_hint_req = urllib.request.Request(
        f"{API_BASE}/api/tutor/chat",
        data=json.dumps({
            "message": f"Topic/Question: {m_quiz['concept']} ({m_quiz['text']}) | Student Inquiry: Can you give me a hint for this question?",
            "time_taken": 15,
            "consecutive_errors": 0,
            "current_tier": "Class 10",
            "current_subject": "Mathematics",
            "history": [],
            "current_question": m_quiz,
            "inquiry_type": "hint"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    m_hint = json.loads(urllib.request.urlopen(m_hint_req).read().decode("utf-8"))
    print(f"Hint Node: {m_hint['active_node']} | Depth: {m_hint['depth_level']}")
    print(f"Hint Text:\n{m_hint['response']}")
    assert "50 Newtons" not in m_hint['response'], "FAILURE: 50 Newtons in Math hint!"
    assert "x = 8" not in m_hint['response'], "FAILURE: Answer leaked in Math hint!"
    assert m_hint['active_node'] == "Socratic Hint Node", f"FAILURE: Expected Socratic Hint Node, got {m_hint['active_node']}"

    # Math Solution
    m_sol_req = urllib.request.Request(
        f"{API_BASE}/api/tutor/chat",
        data=json.dumps({
            "message": f"Topic/Question: {m_quiz['concept']} ({m_quiz['text']}) | Student Inquiry: give me the answer please and show full solution",
            "time_taken": 15,
            "consecutive_errors": 0,
            "current_tier": "Class 10",
            "current_subject": "Mathematics",
            "history": [],
            "current_question": m_quiz,
            "inquiry_type": "solution"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    m_sol = json.loads(urllib.request.urlopen(m_sol_req).read().decode("utf-8"))
    print(f"\nSolution Node: {m_sol['active_node']} | Depth: {m_sol['depth_level']}")
    print(f"Solution Text:\n{m_sol['response']}")
    assert "50 Newtons" not in m_sol['response'], "FAILURE: 50 Newtons in Math solution!"
    assert "x = 8" in m_sol['response'], "FAILURE: x = 8 not in Math solution!"
    assert m_sol['active_node'] == "Direct Explainer Node", f"FAILURE: Expected Direct Explainer Node, got {m_sol['active_node']}"

    # -------------------------------------------------------------
    # 3. PHYSICS CLASS 10 Q1 TEST
    # -------------------------------------------------------------
    print("\n--- 3. Testing Physics (Class 10 Q1) ---")
    req_p = urllib.request.Request(
        f"{API_BASE}/api/tutor/load-theory",
        data=json.dumps({"current_subject": "Physics", "current_tier": "Class 10"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    theory_p = json.loads(urllib.request.urlopen(req_p).read().decode("utf-8"))
    p_quiz = theory_p["quizzes"][0]
    
    # Physics Hint
    p_hint_req = urllib.request.Request(
        f"{API_BASE}/api/tutor/chat",
        data=json.dumps({
            "message": f"Topic/Question: {p_quiz['concept']} ({p_quiz['text']}) | Student Inquiry: Can you give me a hint for this question?",
            "time_taken": 15,
            "consecutive_errors": 0,
            "current_tier": "Class 10",
            "current_subject": "Physics",
            "history": [],
            "current_question": p_quiz,
            "inquiry_type": "hint"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    p_hint = json.loads(urllib.request.urlopen(p_hint_req).read().decode("utf-8"))
    print(f"Hint Node: {p_hint['active_node']} | Depth: {p_hint['depth_level']}")
    print(f"Hint Text:\n{p_hint['response']}")
    assert "50 Newtons" not in p_hint['response'], "FAILURE: 50 Newtons leaked in Physics hint!"
    assert p_hint['active_node'] == "Socratic Hint Node", f"FAILURE: Expected Socratic Hint Node, got {p_hint['active_node']}"

    # Physics Solution
    p_sol_req = urllib.request.Request(
        f"{API_BASE}/api/tutor/chat",
        data=json.dumps({
            "message": f"Topic/Question: {p_quiz['concept']} ({p_quiz['text']}) | Student Inquiry: give me the answer please and show full solution",
            "time_taken": 15,
            "consecutive_errors": 0,
            "current_tier": "Class 10",
            "current_subject": "Physics",
            "history": [],
            "current_question": p_quiz,
            "inquiry_type": "solution"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    p_sol = json.loads(urllib.request.urlopen(p_sol_req).read().decode("utf-8"))
    print(f"\nSolution Node: {p_sol['active_node']} | Depth: {p_sol['depth_level']}")
    print(f"Solution Text:\n{p_sol['response']}")
    assert "50 Newtons" in p_sol['response'], "FAILURE: 50 Newtons not in Physics solution!"
    assert p_sol['active_node'] == "Direct Explainer Node", f"FAILURE: Expected Direct Explainer Node, got {p_sol['active_node']}"

    print("\n" + "=" * 70)
    print("ALL TUTOR HINT & SOLUTION VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    run_test()
