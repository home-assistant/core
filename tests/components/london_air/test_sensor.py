"""Tests for the London Air sensor platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.london_air.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the sensor reports the authority air quality band."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "Low"
    assert state.attributes["sites"] == 2
    assert state.attributes["updated"] == "2017-08-03 03:00:00"
    data = state.attributes["data"]
    assert len(data) == 2
    assert data[0]["site_code"] == "ME2"
    assert data[0]["site_name"] == "Merton Road"
    assert data[0]["pollutants"][0]["code"] == "PM10"
    assert data[0]["pollutants"][0]["summary"] == "PM10 is Low"


async def test_sensor_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the sensor becomes unavailable when a refresh fails."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientConnectorError(Mock(), OSError("test"))
        )
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "unavailable"


async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Test setup retries when the API is unavailable."""
    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientConnectorError(Mock(), OSError("test"))
        )
    )

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_yaml_migration(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test YAML setup imports a config entry and keeps the legacy entity ID."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "london_air", "locations": ["Merton"]}},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == DOMAIN

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "Low"


async def test_yaml_migration_import_failure(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_session: MagicMock,
) -> None:
    """Test YAML setup registers a repair issue when the import fails."""
    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientConnectorError(Mock(), OSError("test"))
        )
    )

    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "london_air", "locations": ["Merton"]}},
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0

    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )

    assert hass.states.get("sensor.merton") is None
