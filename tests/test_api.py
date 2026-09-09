import os
import tempfile
import unittest

from fastapi.testclient import TestClient

import main
import platform_db


class ApiJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        db_path = os.path.join(cls.temp.name, "test.db")
        main.DB_PATH = db_path
        platform_db.DB_PATH = db_path
        cls.client_context = TestClient(main.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        cls.temp.cleanup()

    def create_profile(self, **overrides):
        payload = {
            "first_name": "Amina",
            "career_id": "boda-boda",
            "custom_career": None,
            "career_stage": "Early-career",
            "industry": "Transport & Logistics",
            "region": "Kenya",
            "education_level": None,
            "years_experience": 3,
        }
        payload.update(overrides)
        response = self.client.post("/api/v2/profiles", json=payload)
        self.assertEqual(201, response.status_code, response.text)
        return response.json()

    def test_health_security_headers_and_fuzzy_search(self):
        response = self.client.get("/api/v2/ready")
        self.assertEqual(200, response.status_code)
        self.assertEqual("nosniff", response.headers["x-content-type-options"])
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        search = self.client.get("/api/v2/careers", params={"q": "mechnic"}).json()
        self.assertEqual("Auto Mechanic", search["careers"][0]["canonical_title"])

    def test_complete_resume_and_delete_journey(self):
        created = self.create_profile()
        headers = {"X-Session-Token": created["access_token"]}
        base = f"/api/v2/profiles/{created['session_id']}"
        started = self.client.post(base + "/assessments", headers=headers, json={})
        self.assertEqual(201, started.status_code, started.text)
        assessment = started.json()
        self.assertEqual("Boda Boda Operator", assessment["career"]["canonical_title"])
        while assessment["next_question"]:
            response = self.client.post(
                base + f"/assessments/{assessment['assessment_id']}/answers",
                headers=headers,
                json={"question_id": assessment["next_question"]["id"], "answer_index": 2},
            )
            self.assertEqual(200, response.status_code, response.text)
            assessment = response.json()
        completed = self.client.post(base + f"/assessments/{assessment['assessment_id']}/complete", headers=headers, json={})
        self.assertEqual(200, completed.status_code, completed.text)
        result = completed.json()
        self.assertEqual("complete", result["status"])
        self.assertEqual(7, len(result["result"]["dimensions"]))
        resumed = self.client.get(base, headers=headers)
        self.assertEqual("complete", resumed.json()["assessment"]["status"])
        deleted = self.client.delete(base, headers=headers)
        self.assertEqual(204, deleted.status_code)
        self.assertEqual(401, self.client.get(base, headers=headers).status_code)

    def test_answer_submission_is_idempotent(self):
        created = self.create_profile(first_name="Tariq", career_id="accountant", industry="Business & Finance")
        headers = {"X-Session-Token": created["access_token"]}
        base = f"/api/v2/profiles/{created['session_id']}"
        assessment = self.client.post(base + "/assessments", headers=headers, json={}).json()
        question = assessment["next_question"]
        path = base + f"/assessments/{assessment['assessment_id']}/answers"
        first = self.client.post(path, headers=headers, json={"question_id": question["id"], "answer_index": 1})
        second = self.client.post(path, headers=headers, json={"question_id": question["id"], "answer_index": 3})
        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertEqual(1, second.json()["progress"]["answered"])
        self.assertEqual(3, second.json()["answers"][question["id"]])

    def test_validation_and_unauthorized_access(self):
        invalid = self.client.post("/api/v2/profiles", json={"first_name": "", "career_id": None, "career_stage": "Other", "industry": ""})
        self.assertEqual(422, invalid.status_code)
        created = self.create_profile(first_name="Nia")
        self.assertEqual(401, self.client.get(f"/api/v2/profiles/{created['session_id']}").status_code)

    def test_custom_hybrid_career_has_limited_coverage(self):
        created = self.create_profile(career_id="custom-role", custom_career="solar irrigation repairer and farm adviser", industry="Other")
        headers = {"X-Session-Token": created["access_token"]}
        response = self.client.post(f"/api/v2/profiles/{created['session_id']}/assessments", headers=headers, json={})
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual("fallback", response.json()["career"]["evidence"]["coverage"])


if __name__ == "__main__":
    unittest.main()

