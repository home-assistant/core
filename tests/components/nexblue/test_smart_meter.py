"""Tests for NexBlue Smart Meter sensors."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from nexblue_api import (
    EnergyUsage,
    LoadBalancer,
    NexBlueError,
    NexBlueStatisticsNotSupportedError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Only load the sensor platform."""
    with patch("homeassistant.components.nexblue.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_meter_without_chargers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """An account without chargers can show meter values."""
    mock_client.async_list_chargers.return_value = []
    mock_client.async_list_load_balancers.return_value = [
        LoadBalancer("MX123", "Home meter", "meter")
    ]
    mock_client.async_get_energy_usage.side_effect = [
        EnergyUsage("MX123", "daily", "UTC", 1.0, "kWh", []),
        EnergyUsage("MX123", "monthly", "UTC", 2.0, "kWh", []),
        EnergyUsage("MX123", "yearly", "UTC", 3.0, "kWh", []),
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    def state(key: str) -> str:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", "nexblue", f"MX123_{key}"
        )
        assert entity_id is not None
        return hass.states.get(entity_id).state

    assert state("household_consumption_today") == "1.0"
    assert state("household_consumption_month") == "2.0"
    assert state("household_consumption_year") == "3.0"
    mock_client.async_get_power_levels.assert_not_awaited()
    assert mock_client.async_get_energy_usage.await_count == 3
    assert [
        call.args[4] for call in mock_client.async_get_energy_usage.await_args_list
    ] == ["daily", "monthly", "yearly"]


async def test_unsupported_meter_does_not_hide_supported_meter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Unsupported devices do not prevent a supported meter from being created."""
    mock_client.async_list_load_balancers.return_value = [
        LoadBalancer("CX123", "CT", "ct"),
        LoadBalancer("MX123", "Meter", "meter"),
    ]
    mock_client.async_get_energy_usage.side_effect = [
        NexBlueStatisticsNotSupportedError(),
        *[EnergyUsage("MX123", "daily", "UTC", 0.0, "kWh", []) for _ in range(3)],
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id(
            "sensor", "nexblue", "CX123_household_consumption_today"
        )
        is None
    )
    entity_id = entity_registry.async_get_entity_id(
        "sensor", "nexblue", "MX123_household_consumption_today"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "0.0"


async def test_failed_meter_does_not_hide_other_meter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """One device failure does not prevent another device from being displayed."""
    mock_client.async_list_load_balancers.return_value = [
        LoadBalancer("MX1", "Broken", "meter"),
        LoadBalancer("MX2", "Working", "meter"),
    ]
    mock_client.async_get_energy_usage.side_effect = [
        NexBlueError("failed"),
        *[EnergyUsage("MX2", "daily", "UTC", 0.0, "kWh", []) for _ in range(3)],
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id(
            "sensor", "nexblue", "MX1_household_consumption_today"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", "nexblue", "MX2_household_consumption_today"
        )
        is not None
    )
