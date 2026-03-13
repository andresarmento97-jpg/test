import json
import threading
import time
import unittest
from http.client import HTTPConnection

import server


class LocalServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.SERVICE = server.SaaSMVP()
        server.SESSIONS.clear()
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 8010), server.RequestHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=1)

    def request(self, method, path, payload=None, headers=None):
        conn = HTTPConnection("127.0.0.1", 8010, timeout=2)
        req_headers = headers.copy() if headers else {}
        body = None
        if payload is not None:
            req_headers["Content-Type"] = "application/json"
            body = json.dumps(payload)
        conn.request(method, path, body=body, headers=req_headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        response_headers = dict(resp.getheaders())
        conn.close()
        return resp.status, raw, response_headers

    def test_login_and_pages(self):
        # login page
        status, raw, _ = self.request("GET", "/login")
        self.assertEqual(status, 200)
        self.assertIn("Login", raw)

        # protected route without session
        status, _, headers = self.request("GET", "/dashboard")
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "/login")

        # login then access pages
        status, _, headers = self.request(
            "POST",
            "/auth/login",
            payload={"founder_id": "founder-web", "plan": "pro"},
        )
        self.assertEqual(status, 302)
        cookie = headers.get("Set-Cookie", "")
        self.assertIn("session_id=", cookie)

        auth_headers = {"Cookie": cookie.split(";", 1)[0]}
        for page in ["/dashboard", "/materials", "/pipeline"]:
            page_status, page_raw, _ = self.request("GET", page, headers=auth_headers)
            self.assertEqual(page_status, 200)
            self.assertIn("Fundraising SaaS MVP", page_raw)

    def test_end_to_end_matching_flow(self):
        status, raw, _ = self.request("POST", "/founders/f-http/plan?plan=pro")
        self.assertEqual(status, 200)

        status, raw, _ = self.request(
            "POST",
            "/startups",
            {
                "founder_id": "f-http",
                "name": "HTTP Startup",
                "sector": "ai",
                "stage": "seed",
                "geography": "US",
                "round_size_usd": 1500000,
                "traction_metrics": {"users": "200"},
                "links": {},
            },
        )
        self.assertEqual(status, 200)
        startup = json.loads(raw)
        startup_id = startup["data"]["startup"]["startup_id"]

        status, raw, _ = self.request(
            "POST",
            "/investors",
            {
                "fund_name": "HTTP Ventures",
                "contact": "team@http.vc",
                "stage_focus": ["seed"],
                "sectors": ["ai"],
                "geography": ["US"],
                "ticket_min_usd": 500000,
                "ticket_max_usd": 3000000,
                "warmth": "warm",
            },
        )
        self.assertEqual(status, 200)
        created_inv = json.loads(raw)
        investor_id = created_inv["data"]["investor"]["investor_id"]

        status, raw, _ = self.request(
            "PATCH",
            f"/investors/{investor_id}/pipeline",
            {"status": "Contacted", "notes": "Sent intro", "next_step": "Follow up in 3 days"},
        )
        self.assertEqual(status, 200)
        updated = json.loads(raw)
        self.assertEqual(updated["data"]["investor"]["status"], "Contacted")

        status, raw, _ = self.request("POST", f"/match/f-http/{startup_id}")
        self.assertEqual(status, 200)
        match = json.loads(raw)
        self.assertGreaterEqual(match["data"]["total_matches"], 1)


if __name__ == "__main__":
    unittest.main()
