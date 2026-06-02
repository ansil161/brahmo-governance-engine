import os
from typing import Any, Dict, List, Set
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

    def in_(self, column: str, values: List[Any]) -> "TableQuery":
        """Replicates supabase-py IN filter. Maps to PostgREST 'in.(...)'. """
        # format values to string list representation
        val_str = ",".join(str(v) for v in values)
        self.params[column] = f"in.({val_str})"
        return self

    def update(self, data: Dict[str, Any]) -> "TableQuery":
        self.method = "PATCH"
        self.json_data = data
        return self

    def insert(self, data: Any) -> "TableQuery":
        self.method = "POST"
        self.json_data = data
        return self

    def execute(self) -> Any:
        endpoint = f"{self.url}/rest/v1/{self.table_name}"
        
        request_headers = {**self.headers}
        if self.method in ("POST", "PATCH"):
            request_headers["Prefer"] = "return=representation"
            request_headers["Content-Type"] = "application/json"

        with httpx.Client() as client:
            try:
                if self.method == "GET":
                    response = client.get(
                        endpoint, headers=request_headers, params=self.params
                    )
                elif self.method == "POST":
                    response = client.post(
                        endpoint, headers=request_headers, json=self.json_data
                    )
                elif self.method == "PATCH":
                    response = client.patch(
                        endpoint,
                        headers=request_headers,
                        params=self.params,
                        json=self.json_data,
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {self.method}")
                
                response.raise_for_status()
                
                class SupabaseResponse:
                    def __init__(self, data_list):
                        self.data = data_list
                
                if response.status_code == 204:
                    return SupabaseResponse([])
                    
                return SupabaseResponse(response.json())
            except Exception as e:
                logger.error(
                    f"Supabase PostgREST query fail on {self.method} {self.table_name}: {str(e)}"
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
    logger.info("Pulse Router Engine configured with native supabase-py client.")
except ImportError:
    supabase = HTTPPostgrestClient(SUPABASE_URL, SUPABASE_KEY)  # type: ignore
    logger.warning("Pulse Router Engine configured with fallback HTTP PostgREST client.")


def route_pulse_alerts(affected_node_ids: List[str]) -> Dict[str, Any]:
    """
    Routes notification alerts to relevant users based on the departments of affected nodes.
    - Resolves distinct departments of affected_node_ids.
    - Queries users in those departments having role 'HOD' or 'EDITOR'.
    - Bulk inserts notifications into pulse_alerts table.
    """
    if not affected_node_ids:
        logger.info("No affected nodes provided for pulse routing. Skipping.")
        return {
            "status": "success",
            "message": "No affected nodes provided",
            "alerts_created": 0,
            "departments": [],
            "users_notified": [],
        }

    logger.info(f"Routing pulse alerts for affected nodes: {affected_node_ids}")

    # 1. Fetch departments for affected nodes
    try:
        nodes_response = (
            supabase.table("knowledge_nodes")
            .select("department")
            .in_("id", affected_node_ids)
            .execute()
        )
        nodes = nodes_response.data or []
    except Exception as e:
        logger.error(f"Failed to query departments for affected nodes: {str(e)}")
        return {"status": "error", "message": f"Failed to query nodes: {str(e)}", "alerts_created": 0}

    distinct_departments = {
        n.get("department") for n in nodes if n.get("department")
    }

    if not distinct_departments:
        logger.info("No departments identified for the affected nodes. Skipping alert creation.")
        return {
            "status": "success",
            "message": "No departments resolved",
            "alerts_created": 0,
            "departments": [],
            "users_notified": [],
        }

    # 2. Fetch users in distinct departments matching HOD or EDITOR roles
    try:
        users_response = (
            supabase.table("users")
            .select("id, department")
            .in_("department", list(distinct_departments))
            .in_("role", ["HOD", "EDITOR"])
            .execute()
        )
        users = users_response.data or []
    except Exception as e:
        logger.error(f"Failed to query users for pulse notification: {str(e)}")
        return {"status": "error", "message": f"Failed to query users: {str(e)}", "alerts_created": 0}

    if not users:
        logger.info("No matching HOD or EDITOR users found for the affected departments. Skipping alert creation.")
        return {
            "status": "success",
            "message": "No matching users found",
            "alerts_created": 0,
            "departments": list(distinct_departments),
            "users_notified": [],
        }

    # 3. Formulate bulk alert inserts
    alerts_to_insert = []
    user_ids_notified = []

    for user in users:
        user_id = user.get("id")
        if not user_id:
            continue
            
        alerts_to_insert.append({
            "org_id": "supra",
            "user_id": user_id,
            "alert_type": "CASCADE",
            "severity": "URGENT",
            "title": "Protocol Update Cascade",
            "body": "Nodes in your department require review due to a supersession.",
            "is_read": False,
        })
        user_ids_notified.append(user_id)

    # 4. Perform bulk insert
    if alerts_to_insert:
        try:
            supabase.table("pulse_alerts").insert(alerts_to_insert).execute()
            logger.info(f"Successfully bulk inserted {len(alerts_to_insert)} alerts into pulse_alerts.")
        except Exception as e:
            logger.error(f"Failed to bulk insert notifications: {str(e)}")
            return {"status": "error", "message": f"Failed to insert alerts: {str(e)}", "alerts_created": 0}

    return {
        "status": "success",
        "alerts_created": len(alerts_to_insert),
        "departments": list(distinct_departments),
        "users_notified": user_ids_notified,
    }
