from unittest.mock import MagicMock, patch
import pytest

from governance.health_score import compute_health_score


@pytest.fixture
def mock_supabase():
    with patch("governance.health_score.supabase") as mock_client:
        yield mock_client


def test_health_score_standard_case(mock_supabase) -> None:
    """
    Test standard calculation metrics:
    - 3 total hierarchy levels, active nodes cover 2 of them -> Coverage = 2/3 = 0.67
    - 4 total active/review nodes:
      - 3 ACTIVE, 1 REVIEW_REQUIRED -> Consistency = 3/4 = 0.75
      - of 3 active: 2 are unexpired (Freshness = 2/4 = 0.5)
    - Node type balance: 1 CONSTRAINT, 1 DECISION, 1 ANTI_PATTERN, 1 FACT -> Balance = 1.0 (stddev = 0)
    """
    mock_levels = MagicMock()
    mock_nodes = MagicMock()

    def mock_table(name: str):
        if name == "hierarchy_levels":
            return mock_levels
        elif name == "knowledge_nodes":
            return mock_nodes
        return MagicMock()

    mock_supabase.table.side_effect = mock_table

    # Mock hierarchy_levels response
    mock_levels.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "L1"}, {"id": "L2"}, {"id": "L3"}
    ]

    # Mock knowledge_nodes query responses:
    # 1. select("hierarchy_level_id") for ACTIVE nodes (used in Coverage)
    # 2. select("status, valid_until, node_type") for all nodes (used in others)
    def mock_nodes_select(columns):
        mock_query = MagicMock()
        
        def mock_eq_org(col, val):
            mock_eq_status_or_exec = MagicMock()
            
            # If there is another .eq, it's the Coverage request
            def mock_eq_status(status_col, status_val):
                mock_exec = MagicMock()
                mock_exec.execute.return_value.data = [
                    {"hierarchy_level_id": "L1"},
                    {"hierarchy_level_id": "L2"},
                    {"hierarchy_level_id": "L1"},  # duplicate level
                ]
                return mock_exec
            
            mock_eq_status_or_exec.eq.side_effect = mock_eq_status
            
            # If no other .eq is called, execute directly (representing select for all nodes)
            mock_eq_status_or_exec.execute.return_value.data = [
                {"status": "ACTIVE", "valid_until": "2030-01-01T00:00:00Z", "node_type": "CONSTRAINT"},
                {"status": "ACTIVE", "valid_until": None, "node_type": "DECISION"},
                {"status": "ACTIVE", "valid_until": "2020-01-01T00:00:00Z", "node_type": "ANTI_PATTERN"},  # expired active
                {"status": "REVIEW_REQUIRED", "valid_until": None, "node_type": "FACT"},
            ]
            return mock_eq_status_or_exec
            
        mock_query.eq.side_effect = mock_eq_org
        return mock_query

    mock_nodes.select.side_effect = mock_nodes_select

    # Execute health score calculation
    score = compute_health_score(org_id="org_123")

    # Verify scores
    # Coverage: 2/3 = 0.67
    assert score["coverage"] == 0.67
    # Freshness: 2 / 4 = 0.50
    assert score["freshness"] == 0.50
    # Consistency: 3 / 4 = 0.75
    assert score["consistency"] == 0.75
    # Balance: counts of CONSTRAINT=1, DECISION=1, ANTI_PATTERN=1, FACT=1 -> mean=1.0, stddev=0.0 -> Balance = 1.0
    assert score["balance"] == 1.0
    # Overall: 0.666... * 0.25 + 0.50 * 0.30 + 1.0 * 0.20 + 0.75 * 0.25
    # Overall: 0.1667 + 0.15 + 0.20 + 0.1875 = 0.7042 -> round(0.7042, 2) = 0.70
    assert score["overall"] == 0.70


def test_health_score_empty_database(mock_supabase) -> None:
    """Verify that calculations default gracefully to 0 or 1 when tables are empty."""
    mock_levels = MagicMock()
    mock_nodes = MagicMock()

    mock_supabase.table.side_effect = lambda name: mock_levels if name == "hierarchy_levels" else mock_nodes

    # Return empty responses
    mock_levels.select.return_value.eq.return_value.execute.return_value.data = []
    
    mock_query_empty = MagicMock()
    mock_query_empty.eq.return_value.execute.return_value.data = []
    mock_query_empty.eq.return_value.eq.return_value.execute.return_value.data = []
    mock_nodes.select.return_value = mock_query_empty

    score = compute_health_score(org_id="empty_org")

    assert score["coverage"] == 0.0
    assert score["freshness"] == 1.0
    assert score["consistency"] == 1.0
    assert score["balance"] == 0.0
    # Overall: (0 * 0.25) + (1 * 0.3) + (0 * 0.2) + (1 * 0.25) = 0.55
    assert score["overall"] == 0.55
