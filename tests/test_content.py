import unittest

from assessment_engine import adapt_question_ids, score_assessment, select_question_ids
from platform_content import fallback_career, get_career, load_questions, search_careers, validate_content


class ContentTests(unittest.TestCase):
    def test_content_schema_and_similarity_validation(self):
        report = validate_content()
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual([], report["warnings"])
        self.assertGreaterEqual(report["coverage"]["careers"], 140)
        self.assertGreaterEqual(report["coverage"]["question_constructs"], 20)
        self.assertGreaterEqual(report["coverage"]["skills"], 30)

    def test_required_emerging_market_roles_are_searchable(self):
        queries = {
            "farmer": "Smallholder Farmer",
            "livestock officer": "Livestock Officer",
            "boda": "Boda Boda Operator",
            "mechnic": "Auto Mechanic",
            "welder": "Welder",
            "electrician": "Electrician",
            "teacher": "Teacher",
            "nurse": "Registered Nurse",
            "clinical officer": "Clinical Officer",
            "lawyer": "Lawyer",
            "accountant": "Accountant",
            "shopkeeper": "Shopkeeper",
            "content creator": "Digital Content Creator",
            "civil servant": "Civil Servant",
            "construction worker": "Construction Worker",
            "technician": "Technician",
            "artisan": "Jua Kali Artisan",
        }
        for query, expected_fragment in queries.items():
            with self.subTest(query=query):
                matches = search_careers(query)
                self.assertTrue(matches)
                self.assertTrue(any(expected_fragment in career["canonical_title"] for career in matches[:5]))

    def test_journey_never_repeats_construct(self):
        questions = {q["id"]: q for q in load_questions()["questions"]}
        profile = {"career_stage": "Founder or self-employed"}
        for career_id in ("nurse", "accountant", "auto-mechanic", "boda-boda", "smallholder-farmer", "graphic-designer"):
            ids = select_question_ids(get_career(career_id), profile)
            constructs = [questions[qid]["construct_id"] for qid in ids]
            self.assertEqual(len(constructs), len(set(constructs)))
            self.assertGreaterEqual(len(ids), 12)
            self.assertLessEqual(len(ids), 16)

    def test_question_routing_is_role_specific_and_answer_adaptive(self):
        profile = {"career_stage": "Early-career"}
        nurse = select_question_ids(get_career("nurse"), profile)
        farmer = select_question_ids(get_career("smallholder-farmer"), profile)
        self.assertNotEqual(nurse, farmer)
        adapted = adapt_question_ids(nurse, {"q_ai_adoption_v1": 0})
        self.assertIn("q_learning_v1", adapted)

    def test_answers_materially_change_scores(self):
        career = get_career("accountant")
        ids = select_question_ids(career, {"career_stage": "Early-career"})
        low = score_assessment(career, ids, {qid: 0 for qid in ids})
        high = score_assessment(career, ids, {qid: 4 for qid in ids})
        self.assertNotEqual(low["dimensions"], high["dimensions"])
        self.assertGreater(high["dimensions"]["career_adaptability"], low["dimensions"]["career_adaptability"])

    def test_unknown_role_uses_explicit_limited_coverage(self):
        career = fallback_career("solar irrigation repairer and farm adviser", "Other")
        self.assertEqual("fallback", career["evidence"]["coverage"])
        ids = select_question_ids(career, {"career_stage": "Career changer"})
        result = score_assessment(career, ids, {qid: 2 for qid in ids})
        self.assertEqual("limited", result["confidence"]["level"])


if __name__ == "__main__":
    unittest.main()

