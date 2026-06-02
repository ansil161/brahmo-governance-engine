import os
from typing import Any, Dict, List, Set, Tuple
from dotenv import load_dotenv
import httpx

from app.core.config import settings
from app.core.logging import logger

load_dotenv()

# Determine credentials
SUPABASE_URL = os.getenv("SUPABASE_URL") or settings.SUPABASE_URL
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or settings.SUPABASE_KEY

# Strip trailing slash from URL for formatting consistency
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

    def update(self, data: Dict[str, Any]) -> "TableQuery":
        self.method = "PATCH"
        self.json_data = data
        return self

    def insert(self, data: Dict[str, Any]) -> "TableQuery":
        self.method = "POST"
        self.json_data = data
        return self

    def execute(self) -> Any:
        endpoint = f"{self.url}/rest/v1/{self.table_name}"
        
        # Build headers
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
                
                # Wrap response to match supabase-py API
                class SupabaseResponse:
                    def __init__(self, data_list):
                        self.data = data_list
                
                # Check for empty response body (PostgREST returns 204 No Content for empty updates)
                if response.status_code == 204:
                    return SupabaseResponse([])
                    
                return SupabaseResponse(response.json())
            except Exception as e:
                logger.error(
                    f"Supabase PostgREST query fail on {self.method} {self.table_name}: {str(e)}"
                )
                raise e


class HTTPPostgrestClient:
    """Mock Supabase client that utilizes PostgREST over HTTPX."""
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
    # Try using the real supabase package client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Cascade Invalidation Engine configured with native supabase-py client.")
except ImportError:
    # Gracefully fall back to PostgREST HTTP implementation
    supabase = HTTPPostgrestClient(SUPABASE_URL, SUPABASE_KEY)  # type: ignore
    logger.warning("Cascade Invalidation Engine configured with fallback HTTP PostgREST client.")


def run_cascade(
    superseded_node_id: str, actor_id: str, max_depth: int = 3
) -> Dict[str, Any]:
    """
    Executes a Breadth-First Search (BFS) starting at superseded_node_id, invalidating
    derived children nodes down to max_depth.
    
    Checks child status guards and performs necessary database updates & audit logs.
    """
    logger.info(
        f"Initializing cascade invalidation for node {superseded_node_id} (Actor: {actor_id}, Max Depth: {max_depth})"
    )

    # Queue contains tuples of (node_id, current_depth)
    queue: List[Tuple[str, int]] = [(superseded_node_id, 0)]
    visited: Set[str] = {superseded_node_id}

    affected_nodes: List[Dict[str, Any]] = []
    skipped_nodes: List[Dict[str, Any]] = []
    max_depth_reached = 0

    while queue:
        current_node_id, depth = queue.pop(0)
        max_depth_reached = max(max_depth_reached, depth)

        # Do not process/walk children beyond the max_depth limit
        if depth >= max_depth:
            continue

        # Query edges table for children (source_id) derived from current_node_id (target_id)
        try:
            edges_response = (
                supabase.table("edges")
                .select("source_id")
                .eq("target_id", current_node_id)
                .eq("edge_type", "DERIVED_FROM")
                .execute()
            )
            edges = edges_response.data or []
        except Exception as e:
            logger.error(f"Error querying edges for node {current_node_id}: {str(e)}")
            continue

        for edge in edges:
            child_id = edge.get("source_id")
            if not child_id or child_id in visited:
                continue

            visited.add(child_id)

            # Query knowledge node current status
            try:
                node_response = (
                    supabase.table("knowledge_nodes")
                    .select("status")
                    .eq("id", child_id)
                    .execute()
                )
                nodes = node_response.data or []
            except Exception as e:
                logger.error(f"Error fetching knowledge node status for child {child_id}: {str(e)}")
                continue

            if not nodes:
                logger.warning(f"Child node {child_id} has edge mapping but no matching record in knowledge_nodes.")
                continue

            child_status = nodes[0].get("status")

            # Guard 1: Legal Hold status (Skip and log reason)
            if child_status == "LEGAL_HOLD":
                try:
                    supabase.table("audit_log").insert({
                        "node_id": child_id,
                        "actor_id": actor_id,
                        "action": "CASCADE_SKIP",
                        "reason": "LEGAL_HOLD prevents status change",
                    }).execute()
                except Exception as e:
                    logger.error(f"Failed to insert audit log for skipped child {child_id}: {str(e)}")

                skipped_nodes.append({
                    "node_id": child_id,
                    "reason": "LEGAL_HOLD prevents status change",
                    "depth": depth + 1,
                })
                continue

            # Guard 2: Already Superseded or Review Required (Skip silently, no logs)
            if child_status in ("SUPERSEDED", "REVIEW_REQUIRED"):
                skipped_nodes.append({
                    "node_id": child_id,
                    "reason": f"Already in {child_status} state",
                    "depth": depth + 1,
                })
                continue

            # Valid Child -> Invalidate and Update status
            try:
                # 1. Update status to REVIEW_REQUIRED
                supabase.table("knowledge_nodes").update(
                    {"status": "REVIEW_REQUIRED"}
                ).eq("id", child_id).execute()

                # 2. Log audit trace
                supabase.table("audit_log").insert({
                    "node_id": child_id,
                    "actor_id": actor_id,
                    "action": "STATUS_CHANGE",
                    "old_value": child_status,
                    "new_value": "REVIEW_REQUIRED",
                }).execute()
            except Exception as e:
                logger.error(f"Failed to execute status update and audit log for child {child_id}: {str(e)}")
                continue

            affected_nodes.append({
                "node_id": child_id,
                "depth": depth + 1,
            })

            # Queue child for downstream traversal
            queue.append((child_id, depth + 1))

    logger.info(
        f"Cascade run complete. Affected: {len(affected_nodes)}, Skipped: {len(skipped_nodes)}, Max Depth Reached: {max_depth_reached}"
    )

    return {
        "source_node_id": superseded_node_id,
        "affected_nodes": affected_nodes,
        "skipped_nodes": skipped_nodes,
        "max_depth_reached": max_depth_reached,
    }
