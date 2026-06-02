import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import httpx

from app.core.config import settings
from app.core.logging import logger

load_dotenv()

# Determine credentials
SUPABASE_URL = os.getenv("SUPABASE_URL") or settings.SUPABASE_URL
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or settings.SUPABASE_KEY

if SUPABASE_URL:
    SUPABASE_URL = SUPABASE_URL.rstrip("/")


class TableQuery:
    """Helper query class replicating the supabase-py fluent syntax."""
    def __init__(self, table_name: str, url: str, headers: Dict[str, str]):
        self.table_name = table_name
        self.url = url
        self.headers = headers
        self.params: Dict[str, Any] = {}
        self.method = "GET"
        self.json_data: Any = None

    def select(self, columns: str) -> "TableQuery":
        self.params["select"] = columns
        return self

    def eq(self, column: str, value: Any) -> "TableQuery":
        self.params[column] = f"eq.{value}"
        return self

    def execute(self) -> Any:
        endpoint = f"{self.url}/rest/v1/{self.table_name}"
        
        request_headers = {**self.headers}
        if self.method in ("POST", "PATCH"):
            request_headers["Content-Type"] = "application/json"

        with httpx.Client() as client:
            try:
                response = client.get(
                    endpoint, headers=request_headers, params=self.params
                )
                response.raise_for_status()
                
                class SupabaseResponse:
                    def __init__(self, data_list):
                        self.data = data_list
                
                return SupabaseResponse(response.json())
            except Exception as e:
                logger.error(
                    f"Supabase PostgREST query fail on GET {self.table_name}: {str(e)}"
                )
                raise e


class HTTPPostgrestClient:
    """Mock Supabase client utilizing PostgREST over HTTPX."""
    def __init__(self, url: str, key: str):
        self.url = url
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }

    def table(self, table_name: str) -> TableQuery:
        return TableQuery(table_name, self.url, self.headers)


# Instantiating the client
try:
    from supabase import create_client, Client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Health Score Engine configured with native supabase-py client.")
except ImportError:
    supabase = HTTPPostgrestClient(SUPABASE_URL, SUPABASE_KEY)  # type: ignore
    logger.warning("Health Score Engine configured with fallback HTTP PostgREST client.")


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string into UTC datetime object."""
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def compute_health_score(org_id: str) -> Dict[str, Any]:
    """
    Computes the 4-dimension Knowledge Health Score for a given organization:
    1. Coverage: active hierarchy levels covered / total levels
    2. Freshness: unexpired active nodes / total active+review nodes
    3. Consistency: active nodes / total active+review nodes
    4. Balance: standard-deviation/mean ratio of different node types
    
    Overall = Coverage*0.25 + Freshness*0.30 + Balance*0.20 + Consistency*0.25
    """
    logger.info(f"Computing knowledge health score for organization: {org_id}")

    # --- 1. COVERAGE CALCULATION ---
    coverage = 0.0
    try:
        # Fetch total hierarchy levels for this org
        levels_response = (
            supabase.table("hierarchy_levels")
            .select("id")
            .eq("org_id", org_id)
            .execute()
        )
        total_levels = len(levels_response.data or [])

        if total_levels > 0:
            # Fetch active nodes to calculate covered hierarchy levels
            active_nodes_response = (
                supabase.table("knowledge_nodes")
                .select("hierarchy_level_id")
                .eq("org_id", org_id)
                .eq("status", "ACTIVE")
                .execute()
            )
            active_nodes = active_nodes_response.data or []
            
            # Distinct hierarchy level IDs covered
            distinct_covered_levels = {
                n.get("hierarchy_level_id")
                for n in active_nodes
                if n.get("hierarchy_level_id")
            }
            
            coverage = len(distinct_covered_levels) / total_levels
        else:
            # Default to 0.0 if no hierarchy levels are registered
            coverage = 0.0
    except Exception as e:
        logger.error(f"Error computing Coverage score: {str(e)}")
        coverage = 0.0

    # --- 2. FRESHNESS, CONSISTENCY, & BALANCE CALCULATION ---
    freshness = 1.0
    consistency = 1.0
    balance = 0.0

    try:
        # Bulk query all nodes for this organization
        nodes_response = (
            supabase.table("knowledge_nodes")
            .select("status, valid_until, node_type")
            .eq("org_id", org_id)
            .execute()
        )
        all_nodes = nodes_response.data or []
        
        # A. FRESHNESS & CONSISTENCY
        nodes_active_or_review = [
            n for n in all_nodes if n.get("status") in ("ACTIVE", "REVIEW_REQUIRED")
        ]
        total_active_or_review = len(nodes_active_or_review)

        if total_active_or_review > 0:
            now = datetime.now(timezone.utc)
            fresh_active_count = 0
            active_count = 0

            for node in nodes_active_or_review:
                if node.get("status") == "ACTIVE":
                    active_count += 1
                    valid_until = parse_datetime(node.get("valid_until"))
                    if valid_until is None or valid_until > now:
                        fresh_active_count += 1

            freshness = fresh_active_count / total_active_or_review
            consistency = active_count / total_active_or_review
        else:
            # Default to 1.0 if there are no active/review nodes
            freshness = 1.0
            consistency = 1.0

        # B. BALANCE
        # Standard node type classifications
        node_types = ["CONSTRAINT", "DECISION", "ANTI_PATTERN", "FACT"]
        counts = {t: 0 for t in node_types}
        
        for node in all_nodes:
            nt = node.get("node_type")
            if nt in counts:
                counts[nt] += 1

        type_counts = list(counts.values())
        mean = sum(type_counts) / len(node_types)

        if mean > 0:
            variance = sum((x - mean) ** 2 for x in type_counts) / len(node_types)
            stddev = math.sqrt(variance)
            balance = 1.0 - (stddev / mean)
        else:
            # Default to 0.0 balance if there are no nodes at all
            balance = 0.0

    except Exception as e:
        logger.error(f"Error computing Freshness, Consistency or Balance: {str(e)}")

    # Ensure bounds: metrics should stay between 0.0 and 1.0
    coverage = max(0.0, min(1.0, coverage))
    freshness = max(0.0, min(1.0, freshness))
    consistency = max(0.0, min(1.0, consistency))
    balance = max(0.0, min(1.0, balance))

    # --- 3. OVERALL SCORE ---
    overall = (coverage * 0.25) + (freshness * 0.30) + (balance * 0.20) + (consistency * 0.25)
    overall = max(0.0, min(1.0, overall))

    return {
        "coverage": round(coverage, 2),
        "freshness": round(freshness, 2),
        "consistency": round(consistency, 2),
        "balance": round(balance, 2),
        "overall": round(overall, 2),
    }
