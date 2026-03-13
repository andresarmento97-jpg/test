import unittest

from app import SaaSMVP


class SaaSMVPTests(unittest.TestCase):
    def setUp(self):
        self.svc = SaaSMVP()

    def test_free_plan_cannot_match(self):
        startup_resp = self.svc.upsert_startup(
            {
                "founder_id": "f1",
                "name": "Acme",
                "sector": "fintech",
                "stage": "seed",
                "geography": "US",
                "round_size_usd": 1500000,
                "traction_metrics": {"mrr": "$20k"},
                "links": {"deck": "https://example.com/deck"},
            }
        )
        startup_id = startup_resp["data"]["startup"]["startup_id"]
        match = self.svc.generate_matches("f1", startup_id)
        self.assertFalse(match["ok"])
        self.assertEqual(match["error"]["code"], "payment_required")

    def test_pro_plan_matching_returns_structured_json(self):
        self.svc.set_plan("f2", "pro")
        startup_id = self.svc.upsert_startup(
            {
                "founder_id": "f2",
                "name": "Beta",
                "sector": "ai",
                "stage": "seed",
                "geography": "US",
                "round_size_usd": 2000000,
                "traction_metrics": {"growth": "12% MoM"},
                "links": {},
            }
        )["data"]["startup"]["startup_id"]

        self.svc.create_investor(
            {
                "fund_name": "North Star Ventures",
                "contact": "partner@northstar.vc",
                "stage_focus": ["seed"],
                "sectors": ["ai"],
                "geography": ["US"],
                "ticket_min_usd": 500000,
                "ticket_max_usd": 3000000,
                "warmth": "warm",
            }
        )
        match = self.svc.generate_matches("f2", startup_id)
        self.assertTrue(match["ok"])
        self.assertGreaterEqual(match["data"]["total_matches"], 1)
        self.assertTrue(match["pricing"]["consumes_match_credit"])

    def test_materials_quota_enforced(self):
        founder_id = "f3"
        for _ in range(5):
            ok = self.svc.generate_email(
                {
                    "founder_id": founder_id,
                    "startup_summary": "AI tooling for legal teams.",
                    "raise_amount": "$1M pre-seed",
                    "traction": "20 pilots",
                }
            )
            self.assertTrue(ok["ok"])
        over = self.svc.generate_email(
            {
                "founder_id": founder_id,
                "startup_summary": "AI tooling for legal teams.",
                "raise_amount": "$1M pre-seed",
                "traction": "20 pilots",
            }
        )
        self.assertFalse(over["ok"])
        self.assertEqual(over["error"]["code"], "payment_required")


if __name__ == "__main__":
    unittest.main()
