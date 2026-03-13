from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import uuid4


PIPELINE_STATUSES = ["To Contact", "Contacted", "Meeting", "Term Sheet", "Passed"]
PLANS = ["free", "pro", "premium"]
WARMTH_VALUES = ["cold", "warm", "close"]

PLAN_LIMITS = {
    "free": {"materials_per_month": 5, "match_credits": 0},
    "pro": {"materials_per_month": 20, "match_credits": 1},
    "premium": {"materials_per_month": 100, "match_credits": 5},
}


@dataclass
class FounderAccount:
    founder_id: str
    plan: str = "free"
    month_key: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m"))
    materials_uses: int = 0
    match_credits_used: int = 0


@dataclass
class StartupProfile:
    founder_id: str
    name: str
    sector: str
    stage: str
    geography: str
    round_size_usd: int
    traction_metrics: Dict[str, str]
    links: Dict[str, str]
    startup_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class InvestorRecord:
    fund_name: str
    contact: str
    stage_focus: List[str]
    sectors: List[str]
    geography: List[str]
    ticket_min_usd: int
    ticket_max_usd: int
    notes: str = ""
    warmth: str = "cold"
    status: str = "To Contact"
    last_contact_date: Optional[str] = None
    next_step: Optional[str] = None
    investor_id: str = field(default_factory=lambda: str(uuid4()))


class SaaSMVP:
    def __init__(self) -> None:
        self.founders: Dict[str, FounderAccount] = {}
        self.startups: Dict[str, StartupProfile] = {}
        self.investors: Dict[str, InvestorRecord] = {}

    def _refresh_month(self, founder: FounderAccount) -> None:
        current = datetime.utcnow().strftime("%Y-%m")
        if founder.month_key != current:
            founder.month_key = current
            founder.materials_uses = 0
            founder.match_credits_used = 0

    def _get_or_create_founder(self, founder_id: str) -> FounderAccount:
        founder = self.founders.get(founder_id)
        if not founder:
            founder = FounderAccount(founder_id=founder_id)
            self.founders[founder_id] = founder
        self._refresh_month(founder)
        return founder

    def _error(self, message: str, code: str = "bad_request") -> Dict:
        return {"ok": False, "error": {"code": code, "message": message}}

    def set_plan(self, founder_id: str, plan: str) -> Dict:
        if plan not in PLANS:
            return self._error("Invalid plan")
        founder = self._get_or_create_founder(founder_id)
        founder.plan = plan
        return {
            "ok": True,
            "data": {"founder": asdict(founder)},
            "ui": {"banner": f"Plan switched to {plan.title()}"},
            "pricing": PLAN_LIMITS[plan],
        }

    def upsert_startup(self, payload: Dict) -> Dict:
        required = ["founder_id", "name", "sector", "stage", "geography", "round_size_usd", "traction_metrics", "links"]
        if any(key not in payload for key in required):
            return self._error("Missing startup profile fields")
        startup = StartupProfile(**payload)
        self.startups[startup.startup_id] = startup
        self._get_or_create_founder(startup.founder_id)
        return {
            "ok": True,
            "data": {"startup": asdict(startup)},
            "ui": {"message": "Startup profile saved"},
            "pricing": {"consumes_match_credit": False},
        }

    def create_investor(self, payload: Dict) -> Dict:
        required = ["fund_name", "contact", "stage_focus", "sectors", "geography", "ticket_min_usd", "ticket_max_usd"]
        if any(key not in payload for key in required):
            return self._error("Missing investor fields")
        warmth = payload.get("warmth", "cold")
        if warmth not in WARMTH_VALUES:
            return self._error("Invalid warmth")
        investor = InvestorRecord(**payload)
        self.investors[investor.investor_id] = investor
        return {
            "ok": True,
            "data": {"investor": asdict(investor)},
            "ui": {"message": "Investor added to CRM"},
            "pricing": {"consumes_match_credit": False},
        }

    def list_investors(self, filters: Optional[Dict] = None) -> Dict:
        filters = filters or {}
        results = []
        for inv in self.investors.values():
            if filters.get("stage") and filters["stage"] not in inv.stage_focus:
                continue
            if filters.get("sector") and filters["sector"] not in inv.sectors:
                continue
            if filters.get("geography") and filters["geography"] not in inv.geography:
                continue
            if filters.get("status") and filters["status"] != inv.status:
                continue
            results.append(asdict(inv))
        return {
            "ok": True,
            "data": {"investors": results, "count": len(results)},
            "ui": {"table": "investor pipeline"},
            "pricing": {"consumes_match_credit": False},
        }

    def update_pipeline(self, investor_id: str, status: str, notes: Optional[str] = None, next_step: Optional[str] = None) -> Dict:
        if status not in PIPELINE_STATUSES:
            return self._error("Invalid pipeline status")
        inv = self.investors.get(investor_id)
        if not inv:
            return self._error("Investor not found", code="not_found")
        inv.status = status
        inv.last_contact_date = str(date.today())
        if notes is not None:
            inv.notes = notes
        if next_step is not None:
            inv.next_step = next_step
        return {
            "ok": True,
            "data": {"investor": asdict(inv)},
            "ui": {"message": "Pipeline updated"},
            "pricing": {"consumes_match_credit": False},
        }

    def _match_score(self, startup: StartupProfile, investor: InvestorRecord) -> int:
        score = 0
        if startup.stage in investor.stage_focus:
            score += 3
        if startup.sector in investor.sectors:
            score += 3
        if startup.geography in investor.geography:
            score += 2
        if investor.ticket_min_usd <= startup.round_size_usd <= investor.ticket_max_usd:
            score += 3
        if investor.warmth == "close":
            score += 2
        elif investor.warmth == "warm":
            score += 1
        return score

    def generate_matches(self, founder_id: str, startup_id: str) -> Dict:
        founder = self._get_or_create_founder(founder_id)
        startup = self.startups.get(startup_id)
        if not startup:
            return self._error("Startup not found", code="not_found")
        if founder.plan == "free":
            return self._error("Upgrade required for investor matching", code="payment_required")
        if founder.match_credits_used >= PLAN_LIMITS[founder.plan]["match_credits"]:
            return self._error("No monthly match credits left", code="payment_required")

        ranked = []
        for inv in self.investors.values():
            score = self._match_score(startup, inv)
            if score >= 7:
                ranked.append((score, inv))
        ranked.sort(key=lambda x: x[0], reverse=True)
        top = ranked[:30]
        founder.match_credits_used += 1

        matches = [{
            "investor_id": inv.investor_id,
            "fund_name": inv.fund_name,
            "contact": inv.contact,
            "score": score,
            "warmth": inv.warmth,
            "status": inv.status,
        } for score, inv in top]

        return {
            "ok": True,
            "data": {"founder_id": founder_id, "startup_id": startup_id, "matches": matches, "total_matches": len(matches)},
            "ui": {"headline": "Top 30 Relevant Investors"},
            "pricing": {
                "consumes_match_credit": True,
                "match_credits_used": founder.match_credits_used,
                "match_credits_remaining": PLAN_LIMITS[founder.plan]["match_credits"] - founder.match_credits_used,
            },
        }

    def _check_materials_quota(self, founder: FounderAccount) -> Optional[Dict]:
        if founder.materials_uses >= PLAN_LIMITS[founder.plan]["materials_per_month"]:
            return self._error("Monthly materials limit reached", code="payment_required")
        return None

    def generate_email(self, payload: Dict) -> Dict:
        for field_name in ["founder_id", "startup_summary", "raise_amount", "traction"]:
            if field_name not in payload:
                return self._error("Missing material fields")
        founder = self._get_or_create_founder(payload["founder_id"])
        err = self._check_materials_quota(founder)
        if err:
            return err
        founder.materials_uses += 1
        ask = payload.get("ask", "")
        subject_seed = payload["startup_summary"].split(".")[0]
        email = (
            f"Subject: {subject_seed} — raising {payload['raise_amount']}\n\n"
            f"Hi [Investor Name],\n"
            f"I am building {payload['startup_summary']}. We are raising {payload['raise_amount']}.\n"
            f"Current traction: {payload['traction']}.\n"
            f"Would you be open to a quick intro call? {ask}".strip()
        )
        return {
            "ok": True,
            "data": {"email": email},
            "ui": {"tone": "professional", "length": "concise"},
            "pricing": {
                "consumes_material_credit": True,
                "materials_used": founder.materials_uses,
                "materials_remaining": PLAN_LIMITS[founder.plan]["materials_per_month"] - founder.materials_uses,
            },
        }

    def generate_monthly_update(self, payload: Dict) -> Dict:
        for field_name in ["founder_id", "metrics", "highlights", "asks"]:
            if field_name not in payload:
                return self._error("Missing update fields")
        founder = self._get_or_create_founder(payload["founder_id"])
        err = self._check_materials_quota(founder)
        if err:
            return err
        founder.materials_uses += 1
        metrics = "\n".join(f"- {k}: {v}" for k, v in payload["metrics"].items())
        highlights = "\n".join(f"- {h}" for h in payload["highlights"])
        asks = "\n".join(f"- {a}" for a in payload["asks"])
        update = (
            "Monthly Investor Update\n\n"
            "Key Metrics\n"
            f"{metrics}\n\n"
            "Highlights\n"
            f"{highlights}\n\n"
            "Asks\n"
            f"{asks}"
        )
        return {
            "ok": True,
            "data": {"update": update},
            "ui": {"format": "email-ready"},
            "pricing": {
                "consumes_material_credit": True,
                "materials_used": founder.materials_uses,
                "materials_remaining": PLAN_LIMITS[founder.plan]["materials_per_month"] - founder.materials_uses,
            },
        }

    def improve_deck(self, payload: Dict) -> Dict:
        if "founder_id" not in payload or "raw_content" not in payload:
            return self._error("Missing deck fields")
        founder = self._get_or_create_founder(payload["founder_id"])
        err = self._check_materials_quota(founder)
        if err:
            return err
        founder.materials_uses += 1
        suggestions = [
            "Lead with a one-line problem statement and quantifiable pain.",
            "Keep each slide to one core message and one supporting metric.",
            "Add a clear go-to-market slide with acquisition channels and CAC assumptions.",
            "Include fundraising ask, use of funds, and 18-month milestones.",
        ]
        rewrite = (
            "Investor-ready outline:\n"
            "1) Problem\n2) Solution\n3) Market\n4) Traction\n5) GTM\n6) Financials\n7) Ask\n\n"
            f"Source excerpt:\n{payload['raw_content'][:400]}"
        )
        return {
            "ok": True,
            "data": {"suggestions": suggestions, "rewrite": rewrite},
            "ui": {"focus": ["clarity", "brevity", "investor-readiness"]},
            "pricing": {
                "consumes_material_credit": True,
                "materials_used": founder.materials_uses,
                "materials_remaining": PLAN_LIMITS[founder.plan]["materials_per_month"] - founder.materials_uses,
            },
        }
