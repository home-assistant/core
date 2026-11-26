"""Tests for the Jellyfin sensor platform."""

from datetime import timedelta
import logging
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from jellyfin_apiclient_python.exceptions import HTTPException
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
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


@pytest.mark.parametrize(
    ("status", "log_level", "message"),
    [
        (
            "ServerUnreachable",
            logging.INFO,
            "jellyfin is unavailable: Unable to reach the Jellyfin server",
        ),
        (
            503,
            logging.ERROR,
            "Error fetching jellyfin data: "
            "Error communicating with the Jellyfin server: 503",
        ),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    status: str | int,
    log_level: int,
    message: str,
) -> None:
    """Test the sensor becomes unavailable when fetching data fails."""
    entity_id = "sensor.jellyfin_server_active_clients"
    assert hass.states.get(entity_id).state == "5"

    mock_api.sessions.side_effect = HTTPException(status, "error")
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert ("homeassistant.components.jellyfin", log_level, message) in (
        caplog.record_tuples
    )
    assert "Unexpected error" not in caplog.text

    mock_api.sessions.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "5"
