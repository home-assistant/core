"""Tests for the Jellyfin sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from jellyfin_apiclient_python.exceptions import HTTPException
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_watching(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
) -> None:
    """Test the Jellyfin watching sensor."""
    state = hass.states.get("sensor.jellyfin_server_active_clients")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "JELLYFIN-SERVER Active clients"
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.state == "5"

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.entity_category is None
    assert entry.unique_id == "SERVER-UUID-watching"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.connections == set()
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "SERVER-UUID")}
    assert device.manufacturer == "Jellyfin"
    assert device.name == "JELLYFIN-SERVER"
    assert device.sw_version is None


async def test_server_offline(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the sensor becomes unavailable while the server is offline."""
    mock_api.sessions.side_effect = HTTPException("ServerUnreachable", "offline")

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.jellyfin_server_active_clients")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert (
        "Unable to fetch sessions from the Jellyfin server: ServerUnreachable"
        in caplog.text
    )
    assert "Unexpected error fetching jellyfin data" not in caplog.text

    mock_api.sessions.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.jellyfin_server_active_clients")
    assert state
    assert state.state == "5"


async def test_server_unauthorized(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rejected token starts reauthentication."""
    mock_api.sessions.side_effect = HTTPException("Unauthorized", "token revoked")

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == init_integration.entry_id
