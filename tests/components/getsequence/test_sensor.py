"""Test the Sequence sensor platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.getsequence.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from .fixtures import (
    get_mock_sequence_cash_flow_data,
    get_mock_sequence_data,
    get_mock_sequence_data_with_errors,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_sequence_data():
    """Mock Sequence API data with multiple account types."""
    return get_mock_sequence_data()


async def test_sensor_setup(hass: HomeAssistant, mock_sequence_data) -> None:
    """Test sensor platform setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=mock_sequence_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Test basic sensors that should be enabled (not disabled by default)
    enabled_sensors = [
        # Main aggregate sensors (always enabled)
        "sensor.sequence_account_net_balance",
        "sensor.sequence_account_pods_total_balance",
        "sensor.sequence_account_liabilities_total_balance",
        "sensor.sequence_account_investments_total_balance",
        "sensor.sequence_account_income_sources_total_balance",
        "sensor.sequence_account_external_total_balance",
        "sensor.sequence_account_data_age",
        # Only daily net balance utility meter is enabled by default
        "sensor.sequence_account_cash_flow_daily",
        # Individual account balance sensors (enabled)
        "sensor.test_pod_1_balance",
        "sensor.test_pod_2_balance",
        "sensor.income_account_1_income_source_balance",
        "sensor.income_account_2_income_source_balance",
        "sensor.external_bank_external_balance",
        "sensor.mortgage_account_external_balance",
        "sensor.brokerage_account_external_balance",
    ]

    for sensor_id in enabled_sensors:
        state = hass.states.get(sensor_id)
        assert state is not None, f"Sensor {sensor_id} should exist"

    # Test that disabled utility meters are registered but not active entities
    disabled_sensors = [
        "sensor.sequence_account_cash_flow_weekly",
        "sensor.sequence_account_cash_flow_monthly",
        "sensor.sequence_account_cash_flow_yearly",
        "sensor.test_pod_1_cash_flow_daily",
        "sensor.test_pod_2_cash_flow_daily",
        "sensor.sequence_account_income_sources_cash_flow_daily",
        "sensor.sequence_account_pods_cash_flow_daily",
        "sensor.sequence_account_external_cash_flow_daily",
    ]

    # These should be registered in entity registry but not active
    entity_registry = er.async_get(hass)
    for sensor_id in disabled_sensors:
        entity_entry = entity_registry.async_get(sensor_id)
        assert entity_entry is not None, (
            f"Disabled sensor {sensor_id} should be registered"
        )
        assert entity_entry.disabled_by == RegistryEntryDisabler.INTEGRATION, (
            f"Sensor {sensor_id} should be disabled by integration"
        )


async def test_sensor_attributes(hass: HomeAssistant, mock_sequence_data) -> None:
    """Test sensor attributes."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=mock_sequence_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Check pod sensor attributes with new naming
    state = hass.states.get("sensor.test_pod_1_balance")
    assert state.attributes["account_id"] == "5579244"
    assert state.attributes["account_name"] == "Test Pod 1"
    assert state.attributes["account_type"] == "Pod"

    # Check net balance attributes with updated totals
    state = hass.states.get("sensor.sequence_account_net_balance")
    assert state.attributes["pod_count"] == 2
    assert state.attributes["income_source_count"] == 2
    assert state.attributes["description"] == "Total balance across all accounts"
    assert state.attributes["balance_source"] == "total_balance"

    # Check external account sensor (should remain External type when uncategorized)
    state = hass.states.get("sensor.external_bank_external_balance")
    assert state is not None
    assert state.state == "1500.0"
    assert state.attributes["account_type"] == "External"

    # Check that liability and investment totals include native accounts
    state = hass.states.get("sensor.sequence_account_liabilities_total_balance")
    assert state.state == "-850.0"  # Credit Card

    state = hass.states.get("sensor.sequence_account_investments_total_balance")
    assert state.state == "50000.0"  # 401k Account

    # Check external total includes uncategorized external accounts
    state = hass.states.get("sensor.sequence_account_external_total_balance")
    # External Bank (1500) + Mortgage Account (-250000) + Brokerage Account (75000) = -173500
    assert state.state == "-173500.0"


async def test_utility_meter_functionality(hass: HomeAssistant) -> None:
    """Test utility meter sensors for cash flow tracking."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    # Test with cash flow progression data
    cash_flow_data = get_mock_sequence_cash_flow_data()

    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=cash_flow_data[0],  # Initial state
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Initial state - the only enabled utility meter should be net balance daily
        state = hass.states.get("sensor.sequence_account_cash_flow_daily")
        assert state.state == "0.0"  # Should start at 0.0 after establishing baseline

        # Enable a disabled utility meter for testing
        entity_registry = er.async_get(hass)
        # Enable the Test Pod 1 daily cash flow meter
        entity_registry.async_update_entity(
            "sensor.test_pod_1_cash_flow_daily", disabled_by=None
        )
        await hass.async_block_till_done()

        # Force a full reload by reloading the integration to activate the enabled sensor
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    # Update with positive cash flow
    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=cash_flow_data[1],  # After positive flow
    ):
        coordinator = config_entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Should track positive flow increases in net balance
        # Net change from initial: Pod +200, Income +300, External -50 = +450 total
        state = hass.states.get("sensor.sequence_account_cash_flow_daily")
        assert float(state.state) == 450.0

        # Individual account utility meter (now enabled)
        state = hass.states.get("sensor.test_pod_1_cash_flow_daily")
        assert state is not None
        assert float(state.state) == 200.0

    # Update with more positive cash flow
    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=cash_flow_data[2],  # More positive flow
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Should accumulate additional positive flow
        # Additional: Pod +200, Income +100, External +100 = +400 more
        # Total: 450 initial + 400 more = 850
        state = hass.states.get("sensor.sequence_account_cash_flow_daily")
        assert float(state.state) == 850.0


async def test_external_account_categorization(hass: HomeAssistant) -> None:
    """Test external account categorization via options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
        options={
            "liability_accounts": ["5579251"],  # Mortgage Account
            "investment_accounts": ["5579252"],  # Brokerage Account
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=get_mock_sequence_data(),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Check that categorized accounts are included in correct totals
        # Debug: Check what the actual values are
        liability_state = hass.states.get(
            "sensor.sequence_account_liabilities_total_balance"
        )
        investment_state = hass.states.get(
            "sensor.sequence_account_investments_total_balance"
        )
        external_state = hass.states.get(
            "sensor.sequence_account_external_total_balance"
        )

        # First verify the basic functionality works
        assert liability_state is not None
        assert investment_state is not None
        assert external_state is not None

        # The test data should show:
        # Default liability balance: Credit Card (-850)
        # Default investment balance: 401k Account (50000)
        # Default external balance: External Bank (1500) + Mortgage (-250000) + Brokerage (75000) = -173500

        # If categorization is working:
        # Liability total should include Credit Card (-850) + Mortgage (-250000) = -250850
        # Investment total should include 401k (50000) + Brokerage (75000) = 125000
        # External total should only include uncategorized External Bank = 1500

        # Check if categorization is applied or if it still shows defaults
        liability_value = float(liability_state.state)
        investment_value = float(investment_state.state)
        external_value = float(external_state.state)

        # Categorization should be working: Mortgage (liability) + Brokerage (investment) are now categorized
        # Expected values with categorization:
        # - Liability: Credit Card (-850) + Mortgage (-250000) = -250850
        # - Investment: 401k (50000) + Brokerage (75000) = 125000
        # - External: Only External Bank (1500) remains uncategorized
        assert liability_value == -250850.0  # Credit Card + Mortgage Account
        assert investment_value == 125000.0  # 401k + Brokerage Account
        assert external_value == 1500.0  # Only External Bank


async def test_error_handling_in_sensors(hass: HomeAssistant) -> None:
    """Test sensor behavior with account balance errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=get_mock_sequence_data_with_errors(),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Pod with balance error should be unavailable
        state = hass.states.get("sensor.test_pod_2_balance")
        assert state.state == "unknown"  # Balance is None when error occurs
        assert state.attributes["balance_error"] == "Connection timeout"

    # Pods total should only include available pods
    state = hass.states.get("sensor.sequence_account_pods_total_balance")
    assert float(state.state) == 1000.0  # Only Test Pod 1


async def test_individual_utility_meters_creation(hass: HomeAssistant) -> None:
    """Test that individual utility meters are created for each account."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=get_mock_sequence_data(),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Check that individual utility meters are registered (even if disabled)
        entity_registry = er.async_get(hass)

        # Income source individual meters (disabled by default)
        expected_income_meters = [
            "sensor.income_account_1_income_source_cash_flow_daily",
            "sensor.income_account_1_income_source_cash_flow_weekly",
            "sensor.income_account_1_income_source_cash_flow_monthly",
            "sensor.income_account_1_income_source_cash_flow_yearly",
            "sensor.income_account_2_income_source_cash_flow_daily",
            "sensor.income_account_2_income_source_cash_flow_weekly",
            "sensor.income_account_2_income_source_cash_flow_monthly",
            "sensor.income_account_2_income_source_cash_flow_yearly",
        ]

        for sensor_id in expected_income_meters:
            entity_entry = entity_registry.async_get(sensor_id)
            assert entity_entry is not None, (
                f"Income utility meter {sensor_id} should be registered"
            )
            assert entity_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

        # External account individual meters (disabled by default)
        expected_external_meters = [
            "sensor.external_bank_external_cash_flow_daily",
            "sensor.external_bank_external_cash_flow_weekly",
            "sensor.external_bank_external_cash_flow_monthly",
            "sensor.external_bank_external_cash_flow_yearly",
            "sensor.mortgage_account_external_cash_flow_daily",
            "sensor.mortgage_account_external_cash_flow_weekly",
            "sensor.mortgage_account_external_cash_flow_monthly",
            "sensor.mortgage_account_external_cash_flow_yearly",
            "sensor.brokerage_account_external_cash_flow_daily",
            "sensor.brokerage_account_external_cash_flow_weekly",
            "sensor.brokerage_account_external_cash_flow_monthly",
            "sensor.brokerage_account_external_cash_flow_yearly",
        ]

        for sensor_id in expected_external_meters:
            entity_entry = entity_registry.async_get(sensor_id)
            assert entity_entry is not None, (
                f"External utility meter {sensor_id} should be registered"
            )
            assert entity_entry.disabled_by == RegistryEntryDisabler.INTEGRATION


async def test_utility_meter_state_class_and_attributes(hass: HomeAssistant) -> None:
    """Test that utility meters have correct state class and attributes."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.api.SequenceApiClient.async_get_accounts",
        return_value=get_mock_sequence_data(),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Check aggregate utility meter attributes (enabled by default)
        state = hass.states.get("sensor.sequence_account_cash_flow_daily")
        assert state is not None
        assert state.attributes["state_class"] == "total"
        assert state.attributes["unit_of_measurement"] == "$"
        assert "period" in state.attributes
        assert state.attributes["period"] == "daily"

        # Enable an individual utility meter to test its attributes
        entity_registry = er.async_get(hass)
        entity_registry.async_update_entity(
            "sensor.income_account_1_income_source_cash_flow_daily", disabled_by=None
        )
        await hass.async_block_till_done()

        # Need to reload the config entry to get the disabled entity to show up
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        # Check individual utility meter attributes
        state = hass.states.get("sensor.income_account_1_income_source_cash_flow_daily")
        assert state is not None
        assert state.attributes["state_class"] == "total"
        assert state.attributes["account_type"] == "Income Source"
        assert state.attributes["period"] == "daily"
        assert "account_id" in state.attributes
        assert "account_name" in state.attributes
