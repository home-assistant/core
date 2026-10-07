"""Test init."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx2
import pytest

from homeassistant.components.iotawatt.const import CONF_LEGACY_ENERGY, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import INPUT_SENSOR

from tests.common import MockConfigEntry


async def test_setup_unload(
    hass: HomeAssistant, mock_iotawatt: MagicMock, entry: MockConfigEntry
) -> None:
    """Test we can setup and unload an entry."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = INPUT_SENSOR
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_connection_failed(
    hass: HomeAssistant, mock_iotawatt: MagicMock, entry: MockConfigEntry
) -> None:
    """Test connection error during startup."""
    mock_iotawatt.connect.side_effect = httpx2.ConnectError("")
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(
    hass: HomeAssistant, mock_iotawatt: MagicMock, entry: MockConfigEntry
) -> None:
    """Test auth error during startup."""
    mock_iotawatt.connect.return_value = False
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_update_failed(
    hass: HomeAssistant, mock_iotawatt: MagicMock, entry: MockConfigEntry
) -> None:
    """Test error while fetching sensor data during startup."""
    mock_iotawatt.update.side_effect = httpx2.HTTPStatusError(
        "", request=MagicMock(), response=MagicMock()
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("entry_options", "issue_expected"),
    [
        pytest.param({}, True, id="legacy"),
        pytest.param({CONF_LEGACY_ENERGY: True}, True, id="legacy-explicit"),
        pytest.param({CONF_LEGACY_ENERGY: False}, False, id="migrated"),
    ],
)
async def test_legacy_energy_issue(
    hass: HomeAssistant,
    mock_iotawatt: MagicMock,
    entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    issue_expected: bool,
) -> None:
    """Test the legacy energy repair issue tracks the config entry option."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, f"legacy_energy_{entry.entry_id}")
    assert (issue is not None) is issue_expected


@pytest.mark.parametrize("entry_options", [{CONF_LEGACY_ENERGY: False}])
async def test_legacy_entities_removed(
    hass: HomeAssistant,
    mock_iotawatt: MagicMock,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test legacy period energy entities are removed once migrated."""
    legacy = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "mock-mac-input-1-WattHours", config_entry=entry
    )
    lifetime = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "mock-mac-input-1-WattHours-lifetime", config_entry=entry
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert entity_registry.async_get(legacy.entity_id) is None
    assert entity_registry.async_get(lifetime.entity_id) is not None


@pytest.mark.parametrize(
    ("entry_options", "expected_total_sensors"),
    [
        pytest.param({}, True, id="legacy"),
        pytest.param({CONF_LEGACY_ENERGY: False}, False, id="migrated"),
    ],
)
async def test_api_energy_sensor_flags(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entry_options: dict[str, Any],
    expected_total_sensors: bool,
) -> None:
    """Test the API is configured according to the legacy energy option."""
    with patch(
        "homeassistant.components.iotawatt.coordinator.Iotawatt"
    ) as mock_iotawatt_class:
        instance = mock_iotawatt_class.return_value
        instance.connect = AsyncMock(return_value=True)
        instance.update = AsyncMock()
        instance.getSensors.return_value = {"sensors": {}}
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert (
        mock_iotawatt_class.call_args.kwargs["includeTotalSensors"]
        is expected_total_sensors
    )
    assert mock_iotawatt_class.call_args.kwargs["includeLifetimeSensors"] is True
