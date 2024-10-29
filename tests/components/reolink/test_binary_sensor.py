"""Test the Reolink binary sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_DUO_MODEL, TEST_NVR_NAME

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


async def test_motion_sensor(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor entity with motion sensor."""
    reolink_connect.model = TEST_DUO_MODEL
    reolink_connect.motion_detected.return_value = True
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_NVR_NAME}_motion_lens_0"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_connect.motion_detected.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    # test webhook callback
    reolink_connect.motion_detected.return_value = True
    reolink_connect.ONVIF_event_callback.return_value = [0]
    webhook_id = config_entry.runtime_data.host.webhook_id
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{webhook_id}", data="test_data")

    assert hass.states.get(entity_id).state == STATE_ON
