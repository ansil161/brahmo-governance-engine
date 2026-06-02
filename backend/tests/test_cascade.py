from unittest.mock import MagicMock, patch
import pytest

from governance.cascade_engine import run_cascade


@pytest.fixture
def mock_supabase():
    with patch("governance.cascade_engine.supabase") as mock_client:
        yield mock_client


def test_cascade_engine_success(mock_supabase) -> None:
    """
    Test cascade engine traverses derived edges and updates valid child nodes.
    
    Graph setup:
      parent -> child_1 (status: ACTIVE)
             -> child_2 (status: LEGAL_HOLD)
      child_1 -> child_1_1 (status: ACTIVE)
    """
    # Create mock tables
    mock_edges = MagicMock()
    mock_nodes = MagicMock()
    mock_audit = MagicMock()

    # Route client table requests
    def mock_table(name: str):
        if name == "edges":
            return mock_edges
        elif name == "knowledge_nodes":
            return mock_nodes
        elif name == "audit_log":
            return mock_audit
        return MagicMock()

    mock_supabase.table.side_effect = mock_table

    # Mock edges response based on current target node:
    # parent (0) -> child_1, child_2
    # child_1 (1) -> child_1_1
    # child_2 (2) -> None
    # child_1_1 (3) -> None
    def mock_edges_select(columns):
        mock_query = MagicMock()
        
        def mock_eq_target(col, val):
            mock_eq_type = MagicMock()
            
            def mock_eq_edge_type(edge_col, edge_val):
                mock_exec = MagicMock()
                if val == "parent":
                    mock_exec.execute.return_value.data = [
                        {"source_id": "child_1"},
                        {"source_id": "child_2"},
                    ]
                elif val == "child_1":
                    mock_exec.execute.return_value.data = [
                        {"source_id": "child_1_1"},
                    ]
                else:
                    mock_exec.execute.return_value.data = []
                return mock_exec
                
            mock_eq_type.eq.side_effect = mock_eq_edge_type
            return mock_eq_type
            
        mock_query.eq.side_effect = mock_eq_target
        return mock_query

    mock_edges.select.side_effect = mock_edges_select

    # Mock nodes query response based on child ID:
    # child_1 -> ACTIVE
    # child_2 -> LEGAL_HOLD
    # child_1_1 -> ACTIVE
    def mock_nodes_select(columns):
        mock_query = MagicMock()
        
        def mock_eq_node(col, val):
            mock_exec = MagicMock()
            if val == "child_1":
                mock_exec.execute.return_value.data = [{"status": "ACTIVE"}]
            elif val == "child_2":
                mock_exec.execute.return_value.data = [{"status": "LEGAL_HOLD"}]
            elif val == "child_1_1":
                mock_exec.execute.return_value.data = [{"status": "ACTIVE"}]
            else:
                mock_exec.execute.return_value.data = []
            return mock_exec
            
        mock_query.eq.side_effect = mock_eq_node
        return mock_query

    mock_nodes.select.side_effect = mock_nodes_select

    # Mock update calls
    mock_nodes_update_query = MagicMock()
    mock_nodes.update.return_value = mock_nodes_update_query
    mock_nodes_update_query.eq.return_value.execute.return_value.data = []

    # Run the cascade engine
    summary = run_cascade(
        superseded_node_id="parent",
        actor_id="test_actor",
        max_depth=3
    )

    # Verify results
    assert summary["source_node_id"] == "parent"
    assert summary["max_depth_reached"] == 2

    # affected nodes: child_1 (depth 1) and child_1_1 (depth 2)
    affected_ids = [n["node_id"] for n in summary["affected_nodes"]]
    assert "child_1" in affected_ids
    assert "child_1_1" in affected_ids
    assert "child_2" not in affected_ids

    # skipped nodes: child_2 (LEGAL_HOLD)
    skipped_ids = [n["node_id"] for n in summary["skipped_nodes"]]
    assert "child_2" in skipped_ids
