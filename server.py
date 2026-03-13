import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from app import SaaSMVP


SERVICE = SaaSMVP()
SESSIONS = {}


LOGIN_HTML = """<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Login | Fundraising SaaS MVP</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 2rem; max-width: 480px; }
      .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }
      label { display:block; margin-top:0.5rem; }
      input, select { width:100%; padding:0.5rem; margin-top:0.25rem; }
      button { margin-top:1rem; padding:0.6rem 0.9rem; }
      .muted { color: #555; font-size: 0.9rem; }
    </style>
  </head>
  <body>
    <h1>Fundraising SaaS MVP</h1>
    <p class=\"muted\">Login to open your founder dashboard.</p>
    <div class=\"card\">
      <form method=\"post\" action=\"/auth/login\">
        <label>Founder ID
          <input name=\"founder_id\" placeholder=\"founder-1\" required />
        </label>
        <label>Plan
          <select name=\"plan\">
            <option value=\"free\">free</option>
            <option value=\"pro\">pro</option>
            <option value=\"premium\">premium</option>
          </select>
        </label>
        <button type=\"submit\">Login</button>
      </form>
    </div>
  </body>
</html>
"""


def dashboard_html(founder_id: str) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Dashboard | Fundraising SaaS MVP</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 2rem; max-width: 900px; }}
      .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
      .links a {{ margin-right: 1rem; }}
      pre {{ background:#f6f8fa; padding:1rem; border-radius:8px; }}
      button {{ padding:0.5rem 0.75rem; }}
    </style>
  </head>
  <body>
    <h1>Welcome, {founder_id}</h1>
    <div class=\"links\">
      <a href=\"/dashboard\">Dashboard</a>
      <a href=\"/materials\">Materials Tool</a>
      <a href=\"/pipeline\">Investor Pipeline</a>
      <a href=\"/auth/logout\">Logout</a>
    </div>

    <div class=\"card\">
      <h3>Health Check</h3>
      <button onclick=\"checkHealth()\">Run</button>
      <pre id=\"health\">Click run</pre>
    </div>

    <script>
      async function checkHealth() {{
        const res = await fetch('/health');
        document.getElementById('health').textContent = JSON.stringify(await res.json(), null, 2);
      }}
    </script>
  </body>
</html>"""


def materials_html(founder_id: str) -> str:
    return f"""<!doctype html>
<html>
  <head><meta charset=\"utf-8\" /><title>Materials | Fundraising SaaS MVP</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 2rem; max-width: 900px; }}
      textarea, input {{ width: 100%; padding:0.5rem; margin-top:0.3rem; }}
      .card {{ border:1px solid #ddd; border-radius:8px; padding:1rem; }}
      pre {{ background:#f6f8fa; padding:1rem; border-radius:8px; }}
    </style>
  </head>
  <body>
    <h1>Materials Generator</h1>
    <p>Logged in as <b>{founder_id}</b>. <a href=\"/dashboard\">Back</a></p>
    <div class=\"card\">
      <label>Startup summary<input id=\"summary\" value=\"AI assistant for sales teams.\"/></label>
      <label>Raise amount<input id=\"raise\" value=\"$2M seed\"/></label>
      <label>Traction<input id=\"traction\" value=\"$40k MRR, 10% MoM growth\"/></label>
      <button onclick=\"genEmail()\">Generate Investor Email</button>
      <pre id=\"out\">Output...</pre>
    </div>
    <script>
      async function genEmail() {{
        const payload = {{
          founder_id: '{founder_id}',
          startup_summary: document.getElementById('summary').value,
          raise_amount: document.getElementById('raise').value,
          traction: document.getElementById('traction').value,
          ask: 'Happy to share our deck.'
        }};
        const res = await fetch('/materials/email', {{
          method: 'POST',
          headers: {{'Content-Type':'application/json'}},
          body: JSON.stringify(payload)
        }});
        document.getElementById('out').textContent = JSON.stringify(await res.json(), null, 2);
      }}
    </script>
  </body>
</html>"""


def pipeline_html(founder_id: str) -> str:
    return f"""<!doctype html>
<html>
  <head><meta charset=\"utf-8\" /><title>Pipeline | Fundraising SaaS MVP</title>
    <style>body {{ font-family: Arial, sans-serif; margin: 2rem; max-width:900px; }} pre {{ background:#f6f8fa; padding:1rem; }}</style>
  </head>
  <body>
    <h1>Investor Pipeline</h1>
    <p>Logged in as <b>{founder_id}</b>. <a href=\"/dashboard\">Back</a></p>
    <button onclick=\"loadInvestors()\">Load Investors</button>
    <pre id=\"table\">No data yet.</pre>
    <script>
      async function loadInvestors() {{
        const res = await fetch('/investors');
        document.getElementById('table').textContent = JSON.stringify(await res.json(), null, 2);
      }}
    </script>
  </body>
</html>"""


def status_for_result(result: dict) -> int:
    if result.get("ok"):
        return 200
    error_code = result.get("error", {}).get("code")
    if error_code == "not_found":
        return 404
    if error_code == "payment_required":
        return 402
    return 400


def is_api_path(path: str) -> bool:
    return path.startswith(("/health", "/investors", "/founders", "/startups", "/match", "/materials"))


class RequestHandler(BaseHTTPRequestHandler):
    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200, headers: dict = None) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str, headers: dict = None) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()

    def _session_id(self):
        cookie = self.headers.get("Cookie", "")
        parts = [p.strip() for p in cookie.split(";") if p.strip()]
        for part in parts:
            if part.startswith("session_id="):
                return part.split("=", 1)[1]
        return None

    def _current_founder(self):
        sid = self._session_id()
        return SESSIONS.get(sid)

    def _require_login(self):
        founder_id = self._current_founder()
        if not founder_id:
            self._redirect("/login")
            return None
        return founder_id

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/preview", "/index.html", "/login"}:
            self._send_html(LOGIN_HTML)
            return

        if parsed.path == "/auth/logout":
            sid = self._session_id()
            if sid in SESSIONS:
                del SESSIONS[sid]
            self._redirect("/login", headers={"Set-Cookie": "session_id=; Path=/; Max-Age=0"})
            return

        if parsed.path in {"/dashboard", "/materials", "/pipeline"}:
            founder_id = self._require_login()
            if not founder_id:
                return
            if parsed.path == "/dashboard":
                self._send_html(dashboard_html(founder_id))
            elif parsed.path == "/materials":
                self._send_html(materials_html(founder_id))
            else:
                self._send_html(pipeline_html(founder_id))
            return

        if parsed.path == "/health":
            self._send_json({"ok": True, "status": "ok"})
            return

        if parsed.path == "/investors":
            query = parse_qs(parsed.query)
            filters = {
                "stage": query.get("stage", [None])[0],
                "sector": query.get("sector", [None])[0],
                "geography": query.get("geography", [None])[0],
                "status": query.get("status", [None])[0],
            }
            result = SERVICE.list_investors(filters)
            self._send_json(result, status_for_result(result))
            return

        if not is_api_path(parsed.path):
            self._send_html(LOGIN_HTML)
            return

        self._send_json({"ok": False, "error": {"code": "not_found", "message": "Route not found"}}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path_parts = [p for p in parsed.path.split("/") if p]

        if parsed.path == "/auth/login":
            content_type = self.headers.get("Content-Type", "")
            founder_id = None
            plan = "free"
            if "application/json" in content_type:
                payload = self._read_json()
                founder_id = payload.get("founder_id")
                plan = payload.get("plan", "free")
            else:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = parse_qs(raw)
                founder_id = form.get("founder_id", [None])[0]
                plan = form.get("plan", ["free"])[0]

            if not founder_id:
                self._send_html("<h1>Missing founder_id</h1>", status=400)
                return

            SERVICE.set_plan(founder_id, plan)
            session_id = str(uuid4())
            SESSIONS[session_id] = founder_id
            self._redirect("/dashboard", headers={"Set-Cookie": f"session_id={session_id}; Path=/; HttpOnly"})
            return

        if len(path_parts) == 3 and path_parts[0] == "founders" and path_parts[2] == "plan":
            founder_id = path_parts[1]
            query = parse_qs(parsed.query)
            payload = self._read_json() if self.headers.get("Content-Length") else {}
            plan = query.get("plan", [payload.get("plan")])[0]
            result = SERVICE.set_plan(founder_id, plan)
            self._send_json(result, status_for_result(result))
            return

        if parsed.path == "/startups":
            result = SERVICE.upsert_startup(self._read_json())
            self._send_json(result, status_for_result(result))
            return

        if parsed.path == "/investors":
            result = SERVICE.create_investor(self._read_json())
            self._send_json(result, status_for_result(result))
            return

        if len(path_parts) == 3 and path_parts[0] == "match":
            founder_id, startup_id = path_parts[1], path_parts[2]
            result = SERVICE.generate_matches(founder_id, startup_id)
            self._send_json(result, status_for_result(result))
            return

        if parsed.path == "/materials/email":
            result = SERVICE.generate_email(self._read_json())
            self._send_json(result, status_for_result(result))
            return

        if parsed.path == "/materials/update":
            result = SERVICE.generate_monthly_update(self._read_json())
            self._send_json(result, status_for_result(result))
            return

        if parsed.path == "/materials/deck":
            result = SERVICE.improve_deck(self._read_json())
            self._send_json(result, status_for_result(result))
            return

        self._send_json({"ok": False, "error": {"code": "not_found", "message": "Route not found"}}, 404)

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) == 3 and path_parts[0] == "investors" and path_parts[2] == "pipeline":
            investor_id = path_parts[1]
            payload = self._read_json()
            result = SERVICE.update_pipeline(
                investor_id,
                status=payload.get("status", ""),
                notes=payload.get("notes"),
                next_step=payload.get("next_step"),
            )
            self._send_json(result, status_for_result(result))
            return
        self._send_json({"ok": False, "error": {"code": "not_found", "message": "Route not found"}}, 404)


def run_server(host: str = "0.0.0.0", port: int = 8000) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"MVP server running on {host}:{port}")
    print(f"Open login page: http://127.0.0.1:{port}/login")
    print("Press CTRL+C to stop.")
    httpd.serve_forever()
    return httpd


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    run_server(host=host, port=port)
