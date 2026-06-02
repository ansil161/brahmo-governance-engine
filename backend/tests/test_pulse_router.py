from unittest.mock import MagicMock, patch
import pytest

from governance.pulse_router import route_pulse_alerts


@pytest.fixture
def mock_supabase():
    with patch("governance.pulse_router.supabase") as mock_client:
        yield mock_client


def test_pulse_router_success(mock_supabase) -> None:
    """
    Test routing pulse alerts for affected nodes:
    - 2 affected nodes belonging to 'Cardiology' and 'Neurology'
    - 3 users in those departments (2 matching HOD/EDITOR roles, 1 other role)
    - Verifies correct alert mappings and bulk insert calls.
    """
    mock_nodes = MagicMock()
    mock_users = MagicMock()
    mock_alerts = MagicMock()

    def mock_table(name: str):
        if name == "knowledge_nodes":
            return mock_nodes
        elif name == "users":
            return mock_users
        elif name == "pulse_alerts":
            return mock_alerts
        return MagicMock()

    mock_supabase.table.side_effect = mock_table

    # Mock knowledge_nodes query
    mock_nodes.select.return_value.in_.return_value.execute.return_value.data = [
        {"department": "Cardiology"},
        {"department": "Neurology"},
        {"department": "Cardiology"},  # duplicate department
    ]

    # Mock users query
    mock_users.select.return_value.in_.return_value.in_.return_value.execute.return_value.data = [
        {"id": "usr_1", "department": "Cardiology"},
        {"id": "usr_2", "department": "Neurology"},
    ]

    # Mock insert call
    mock_alerts.insert.return_value.execute.return_value.data = []

    # Run routing logic
    result = route_pulse_alerts(["node_1", "node_2"])

    # Verify output metrics
    assert result["status"] == "success"
    assert result["alerts_created"] == 2
    assert "Cardiology" in result["departments"]
    assert "Neurology" in result["departments"]
    assert "usr_1" in result["users_notified"]
    assert "usr_2" in result["users_notified"]

    # Verify supabase query chain was triggered
    mock_nodes.select.assert_called_once_with("department")
    mock_users.select.assert_called_once_with("id, department")
    
    # Verify insert data argument was structured correctly
    mock_alerts.insert.assert_called_once()
    inserted_args = mock_alerts.insert.call_args[0][0]
    assert len(inserted_args) == 2
    assert inserted_args[0]["user_id"] == "usr_1"
    assert inserted_args[0]["org_id"] == "supra"
    assert inserted_args[0]["alert_type"] == "CASCADE"
    assert inserted_args[0]["severity"] == "URGENT"


def test_pulse_router_empty_nodes(mock_supabase) -> None:
    """Verify routing skips gracefully and does not execute database queries if node list is empty."""
    result = route_pulse_alerts([])

    assert result["status"] == "success"
    assert result["alerts_created"] == 0
    assert result["departments"] == []
    mock_supabase.table.assert_not_called()
