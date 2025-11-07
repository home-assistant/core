"""Exhaustive behavioral tests for getsequence sensors to exercise real code paths.

These tests construct entities via the exported `build_entities` helper and then call
properties and methods to exercise branches (device_info, native_value, extra_state_attributes,
availability, cash flow accumulation, data age calculations).
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from homeassistant.components.getsequence.sensor import (
    AccountSensor,
    AggregateAccountSensor,
    CashFlowSensor,
    DataAgeSensor,
    build_entities,
)
from homeassistant.const import CONF_ACCESS_TOKEN

from .fixtures import get_mock_sequence_data

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for testing."""
    return MockConfigEntry(
        domain="getsequence", data={CONF_ACCESS_TOKEN: "token"}, unique_id="uid"
    )


class SimpleCoordinator(SimpleNamespace):
    """Simple test coordinator that mimics the data coordinator interface."""

    def __init__(self) -> None:
        """Initialize the coordinator with test data."""
        super().__init__()
        # Get raw mock data
        raw_data = get_mock_sequence_data()
        accounts = raw_data.get("data", {}).get("accounts", [])

        # Process data to match what the real coordinator returns
        # Extract accounts by type
        pods = [acc for acc in accounts if acc.get("type") == "Pod"]
        income_sources = [acc for acc in accounts if acc.get("type") == "Income Source"]
        liabilities = [acc for acc in accounts if acc.get("type") == "Liability"]
        investments = [acc for acc in accounts if acc.get("type") == "Investment"]
        external_accounts = [acc for acc in accounts if acc.get("type") == "External"]

        # Calculate balances
        pod_balance = sum(
            acc.get("balance", {}).get("amountInDollars", 0) or 0
            for acc in pods
            if acc.get("balance", {}).get("error") is None
        )
        income_source_balance = sum(
            acc.get("balance", {}).get("amountInDollars", 0) or 0
            for acc in income_sources
            if acc.get("balance", {}).get("error") is None
        )
        liability_balance = sum(
            acc.get("balance", {}).get("amountInDollars", 0) or 0
            for acc in liabilities
            if acc.get("balance", {}).get("error") is None
        )
        investment_balance = sum(
            acc.get("balance", {}).get("amountInDollars", 0) or 0
            for acc in investments
            if acc.get("balance", {}).get("error") is None
        )
        uncategorized_external_balance = sum(
            acc.get("balance", {}).get("amountInDollars", 0) or 0
            for acc in external_accounts
            if acc.get("balance", {}).get("error") is None
        )

        # Total balance is sum of all account types
        total_balance = (
            pod_balance
            + income_source_balance
            + liability_balance
            + investment_balance
            + uncategorized_external_balance
        )

        # Set processed data structure matching coordinator
        self.data = {
            "accounts": accounts,
            "pods": pods,
            "income_sources": income_sources,
            "liabilities": liabilities,
            "investments": investments,
            "external_accounts": external_accounts,
            "uncategorized_external_accounts": external_accounts,
            "total_balance": total_balance,
            "pod_balance": pod_balance,
            "liability_balance": liability_balance,
            "investment_balance": investment_balance,
            "income_source_balance": income_source_balance,
            "uncategorized_external_balance": uncategorized_external_balance,
        }
        self.last_update_success = True
        self.last_update_success_time = datetime.now(UTC) - timedelta(minutes=5)
        self.update_interval = timedelta(minutes=1)


@pytest.fixture
def simple_coordinator() -> SimpleCoordinator:
    """Return a simple coordinator with mock data for testing."""
    return SimpleCoordinator()


def test_build_entities_and_basic_properties(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test that build_entities creates expected sensor types and basic properties work."""
    entities = build_entities(simple_coordinator, mock_config_entry)

    # Ensure we built a non-empty list and include expected sensor types
    assert any(isinstance(e, AggregateAccountSensor) for e in entities)
    assert any(isinstance(e, AccountSensor) for e in entities)
    assert any(isinstance(e, CashFlowSensor) for e in entities)
    assert any(isinstance(e, DataAgeSensor) for e in entities)

    # Pick one account sensor and exercise its properties
    acct = next(e for e in entities if isinstance(e, AccountSensor))
    di = acct.device_info
    assert "identifiers" in di
    # native_value should reflect coordinator data
    _ = acct.native_value
    _ = acct.extra_state_attributes
    assert acct.available is True


def test_cash_flow_accumulation(
    simple_coordinator: SimpleCoordinator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that cash flow sensors properly accumulate balance changes over time."""
    entities = build_entities(simple_coordinator, mock_config_entry)
    # Find the daily net cash flow sensor
    net_daily = next(
        e
        for e in entities
        if isinstance(e, CashFlowSensor) and e._period == "daily" and e._scope == "net"
    )

    # Initial read should set previous_balance and return 0.0
    v1 = net_daily.native_value
    # First call sets the baseline but returns 0.0
    assert v1 == 0.0

    # Simulate coordinator balance change
    simple_coordinator.data["total_balance"] = (
        simple_coordinator.data.get("total_balance", 0) + 100.0
    )
    v2 = net_daily.native_value
    assert v2 == 100.0

    # Another change accumulates
    simple_coordinator.data["total_balance"] += 50.0
    v3 = net_daily.native_value
    assert v3 == 150.0


def test_aggregate_extra_attributes(
    simple_coordinator: SimpleCoordinator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that aggregate account sensors provide expected extra state attributes."""
    entities = build_entities(simple_coordinator, mock_config_entry)
    agg = next(
        e
        for e in entities
        if isinstance(e, AggregateAccountSensor) and e.balance_key == "pod_balance"
    )
    attrs = agg.extra_state_attributes
    # Should include pod_count and balance_source
    assert "pod_count" in attrs


def test_data_age_sensor(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test that data age sensor correctly calculates time since last update."""
    das = DataAgeSensor(simple_coordinator, mock_config_entry)
    # native_value should be approximately 5 minutes
    v = das.native_value
    assert v is not None and v > 0
    attrs = das.extra_state_attributes
    assert attrs["last_update_success"] == simple_coordinator.last_update_success
    assert attrs["update_interval_minutes"] == pytest.approx(
        simple_coordinator.update_interval.total_seconds() / 60
    )


def test_individual_cash_flow_for_pod(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test individual cash flow sensor functionality for pod accounts."""
    # Find a pod in the data and build an individual cash flow sensor for it
    pods = simple_coordinator.data.get("pods", [])
    if not pods:
        pytest.skip("No pods in fixture data")

    pod = pods[0]
    cfs = CashFlowSensor(
        simple_coordinator,
        mock_config_entry,
        "daily",
        "individual",
        account_data=pod,
        account_type="Pod",
    )
    # First read
    assert cfs.native_value in (None, 0.0)
    # If there is a numeric balance, simulate flow
    if cfs._get_current_balance() is not None:
        simple_coordinator.data["pods"][0]["balance"]["amountInDollars"] = (
            simple_coordinator.data["pods"][0]["balance"].get("amountInDollars", 0) or 0
        ) + 10
        new = cfs.native_value
        assert new is not None


def test_account_sensor_balance_not_numeric(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test AccountSensor returns None when balance value is not numeric."""
    # Test line 368: return current if isinstance(current, (int, float)) else None
    # This line is reached when we successfully navigate the balance path but get a non-numeric value
    # Works for both pods (after error check passes) and non-pods
    pod_data = {
        "id": "pod_non_numeric_123",
        "name": "Pod with String Balance",
        "balance": {
            "amountInDollars": "string_value",
            "error": None,
        },  # No error, but value is string
        "type": "Pod",
    }
    # Replace coordinator pods with our test pod
    simple_coordinator.data["pods"] = [pod_data]

    sensor = AccountSensor(
        simple_coordinator,
        mock_config_entry,
        pod_data,
        "Pod",
        "pods",
        ["balance", "amountInDollars"],
    )
    # Should return None since value is "string_value" not a number
    # Line 368 check: return current if isinstance(current, (int, float)) else None
    value = sensor.native_value
    assert value is None
    # Also verify the account_id matches to ensure we're finding the account
    assert sensor.account_id == "pod_non_numeric_123"


def test_account_sensor_account_not_in_coordinator(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test AccountSensor returns None when account not found in coordinator (line 369)."""
    # Line 369: return None (at end of for loop when no account matches)

    class EmptyCoordinator(SimpleNamespace):
        """Coordinator with no accounts."""

        def __init__(self) -> None:
            """Initialize."""
            super().__init__()
            self.data = {"pods": []}  # Empty list - no accounts
            self.last_update_success = True

    coordinator = EmptyCoordinator()
    pod_data = {"id": "missing_pod", "name": "Missing Pod", "balance": {}}

    sensor = AccountSensor(
        coordinator,
        mock_config_entry,
        pod_data,
        "Pod",
        "pods",
    )
    # Should return None since account doesn't exist in coordinator
    value = sensor.native_value
    assert value is None


def test_account_sensor_extra_attributes_account_not_found(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test AccountSensor returns empty dict when account not found."""
    pod_data = {"id": "9997", "name": "Pod Not Found", "balance": {"error": None}}

    sensor = AccountSensor(
        simple_coordinator,
        mock_config_entry,
        pod_data,
        "Pod",
        "pods",
    )
    # Should return empty dict since account not found
    assert sensor.extra_state_attributes == {}


def test_account_sensor_not_available_when_coordinator_fails(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test AccountSensor returns unavailable when coordinator fails."""
    pod_data = simple_coordinator.data["pods"][0]
    simple_coordinator.last_update_success = False

    sensor = AccountSensor(
        simple_coordinator,
        mock_config_entry,
        pod_data,
        "Pod",
        "pods",
    )
    # Should return False when coordinator fails
    assert sensor.available is False


def test_cash_flow_sensor_non_pod_individual_account(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test CashFlowSensor with non-pod individual account type for line 621 coverage."""
    # Line 621: return account.get("balance") for non-pod individual accounts
    # Create a simple non-pod account with direct balance field
    external_account = {
        "id": "ext_test_123",
        "name": "External Test Account",
        "balance": 9999.99,  # Direct balance, not nested like pods
        "type": "External",
    }
    # Add to coordinator - make sure it's actually there
    simple_coordinator.data["external_accounts"] = [external_account]
    # Verify it's in the coordinator
    assert len(simple_coordinator.data["external_accounts"]) == 1
    assert simple_coordinator.data["external_accounts"][0]["id"] == "ext_test_123"

    sensor = CashFlowSensor(
        simple_coordinator,
        mock_config_entry,
        "daily",
        "individual",
        account_data=external_account,
        account_type="External",
    )
    # Verify account_type is set correctly and is NOT "pod"
    assert sensor.account_type == "External"
    assert sensor.account_type.lower() != "pod"
    assert sensor.account_id == "ext_test_123"
    # Verify _get_data_source returns "external_accounts"
    assert sensor._get_data_source() == "external_accounts"

    # This should hit line 621: return account.get("balance")
    # because External accounts are not pods (line 620: else branch)
    balance = sensor._get_current_balance()
    # If we got None, the account wasn't found in the coordinator
    assert balance is not None, "Balance should not be None - account not found?"
    assert balance == 9999.99

    # Also test with native_value to ensure full code path
    first_value = sensor.native_value
    assert first_value == 0.0  # First call establishes baseline


def test_cash_flow_sensor_liability_data_source(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test CashFlowSensor._get_data_source for liability accounts."""
    liability_data = {"id": "liab1", "name": "Liability"}

    sensor = CashFlowSensor(
        simple_coordinator,
        mock_config_entry,
        "daily",
        "individual",
        account_data=liability_data,
        account_type="Liability",
    )
    # Should return "liabilities"
    assert sensor._get_data_source() == "liabilities"


def test_cash_flow_sensor_unknown_type_data_source(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test CashFlowSensor._get_data_source returns 'accounts' for unknown account type."""
    unknown_data = {"id": "unk1", "name": "Unknown"}

    # Use an account type that doesn't match any of the specific checks in _get_data_source
    # Lines 629-634 check for: "pod", "income", "liability", "external"
    # Line 635: return "accounts" as the default fallback
    sensor = CashFlowSensor(
        simple_coordinator,
        mock_config_entry,
        "daily",
        "individual",
        account_data=unknown_data,
        account_type="SavingsAccount",  # Doesn't contain pod/income/liability/external
    )
    # Should return "accounts" as default (line 635 coverage)
    data_source = sensor._get_data_source()
    assert data_source == "accounts"


def test_cash_flow_sensor_scope_key_non_individual(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test CashFlowSensor._get_scope_key for non-individual scope."""
    sensor = CashFlowSensor(
        simple_coordinator,
        mock_config_entry,
        "daily",
        "net",  # Non-individual scope
    )
    # Should return the scope itself (line 542 coverage)
    assert sensor._get_scope_key() == "net"


def test_cash_flow_sensor_aggregate_extra_attributes(
    simple_coordinator: SimpleCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test CashFlowSensor extra attributes for aggregate scope."""
    sensor = CashFlowSensor(
        simple_coordinator,
        mock_config_entry,
        "daily",
        "aggregate",
        account_type="Pods",
        balance_source="pod_balance",
    )
    attrs = sensor.extra_state_attributes
    # Should include balance_source
    assert "balance_source" in attrs
    assert attrs["balance_source"] == "pod_balance"


def test_data_age_sensor_no_last_update_time(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DataAgeSensor returns None when last_update_success_time is None."""

    class CoordinatorNoTime(SimpleNamespace):
        """Coordinator without last update time."""

        def __init__(self) -> None:
            """Initialize."""
            super().__init__()
            self.last_update_success_time = None
            self.update_interval = None
            self.last_update_success = False

    coordinator = CoordinatorNoTime()
    sensor = DataAgeSensor(coordinator, mock_config_entry)
    # Should return None when no last update time
    assert sensor.native_value is None
