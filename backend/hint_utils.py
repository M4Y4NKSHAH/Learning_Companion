import re


def sanitize_gap_analysis(gap_analysis: str, expected_answer: str = "") -> str:
    """Remove leaked correct answers from diagnostic text shown to students."""
    if not gap_analysis:
        return "Review how the quantities in this problem relate to each other."

    sanitized = gap_analysis
    if expected_answer:
        for variant in {expected_answer, expected_answer.lower(), expected_answer.upper()}:
            sanitized = re.sub(
                rf"expected answer\s+is\s+['\"]?{re.escape(variant)}['\"]?",
                "your result does not yet match the required form",
                sanitized,
                flags=re.IGNORECASE,
            )
            sanitized = sanitized.replace(f"'{variant}'", "the required value")

    sanitized = re.sub(
        r"the (?:correct|expected|right) answer (?:is|was)\s+[^\n.]+",
        "your submission still needs adjustment",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"but the expected answer[^\n.]*",
        "but the approach or result needs revision",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized.strip()


def sanitize_hint_text(hint: str, expected_answer: str = "") -> str:
    """Strip final-answer leaks from tutor hints while preserving guidance."""
    if not hint:
        return hint

    sanitized = hint
    if expected_answer:
        for variant in {expected_answer, expected_answer.lower(), expected_answer.upper()}:
            patterns = [
                rf"(?:the\s+)?(?:correct|final|expected)\s+answer\s+is\s+['\"]?{re.escape(variant)}['\"]?",
                rf"=\s*{re.escape(variant)}\b",
                rf"therefore[,]?\s+(?:the\s+answer\s+is\s+)?{re.escape(variant)}\b",
            ]
            for pattern in patterns:
                sanitized = re.sub(pattern, "[work through the final step yourself]", sanitized, flags=re.IGNORECASE)

    sanitized = re.sub(
        r"(?:the\s+)?(?:correct|final|expected)\s+answer\s+is\s+[^\n.]+",
        "complete the remaining steps to reach the result",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized.strip()


HINT_FORMAT_DIRECTIVE = (
    "\n\nFORMATTING REQUIREMENT:\n"
    "- Respond in clean markdown using short section headers (##), bullet lists (-), and **bold** for key terms.\n"
    "- NEVER state the final numerical result, exact answer string, or completed substitution.\n"
    "- Guide the student to discover the answer themselves."
)


def compute_semantic_similarity(student_ans: str, expected_ans: str) -> float:
    """
    Computes a robust semantic similarity score (0.0 to 1.0) between a student submission
    and expected answer, supporting partial credit grading when offline.
    Combines character/token normalization, numerical tolerance, and TF-IDF cosine similarity.
    """
    if not student_ans or not expected_ans:
        return 0.0

    s_clean = student_ans.strip().lower()
    e_clean = expected_answer_clean = expected_ans.strip().lower()

    # Exact string match
    if s_clean == e_clean:
        return 1.0

    # Normalized match (stripping spaces, common math prefixes like "x=", "ans=")
    s_norm = re.sub(r"^(?:x|ans|answer|result)\s*[:=]\s*", "", s_clean).replace(" ", "")
    e_norm = re.sub(r"^(?:x|ans|answer|result)\s*[:=]\s*", "", e_clean).replace(" ", "")
    if s_norm == e_norm:
        return 1.0

    # Check for direct substring containment (e.g. "nRT" inside "It is equal to nRT")
    if len(e_clean) >= 3 and e_clean in s_clean:
        return 0.95
    if len(s_clean) >= 3 and s_clean in e_clean:
        ratio = len(s_clean) / len(e_clean)
        if ratio >= 0.7:
            return round(0.75 + (0.2 * ratio), 2)

    # Check for numerical value equivalence within ±5% tolerance
    num_pattern = re.compile(r"[-+]?\d+(?:\.\d+)?")
    s_nums = [float(x) for x in num_pattern.findall(s_clean)]
    e_nums = [float(x) for x in num_pattern.findall(e_clean)]
    if s_nums and e_nums and len(s_nums) == len(e_nums):
        matches = True
        for sn, en in zip(s_nums, e_nums):
            tol = max(abs(en) * 0.05, 1e-4)
            if abs(sn - en) > tol:
                matches = False
                break
        if matches:
            return 0.92

    # Word token sets (ignoring basic English stopwords)
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "of", "in", "to", "and", "or", "for", "that", "this", "it", "by", "with", "be"}
    s_words = {w for w in re.findall(r"\w+", s_clean) if w not in stop_words}
    e_words = {w for w in re.findall(r"\w+", e_clean) if w not in stop_words}
    jaccard = (len(s_words & e_words) / len(s_words | e_words)) if (s_words and e_words) else 0.0

    # TF-IDF Cosine Similarity (Word-Level + Character-Level Fallback)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            lowercase=True
        )
        matrix = vectorizer.fit_transform([student_ans, expected_ans])
        sim_word = float(cosine_similarity(matrix[0], matrix[1])[0][0])
        score = max(sim_word, jaccard)
        return round(min(1.0, max(0.0, score)), 3)
    except Exception:
        return round(jaccard, 3)
