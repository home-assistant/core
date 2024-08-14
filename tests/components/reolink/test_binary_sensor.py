"""Test the Reolink binary sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL, const
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import TEST_NVR_NAME, TEST_UID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


async def test_motion_sensor(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor entity with motion sensor."""
    reolink_connect.model = "Reolink Duo PoE"
    reolink_connect.motion_detected.return_value = True
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_NVR_NAME}_motion_lens_0"
    assert hass.states.is_state(entity_id, "on")

    reolink_connect.motion_detected.return_value = False
    async_fire_time_changed(
        hass, utcnow() + DEVICE_UPDATE_INTERVAL + timedelta(seconds=30)
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, "off")

    # test webhook callback
    reolink_connect.motion_detected.return_value = True
    reolink_connect.ONVIF_event_callback.return_value = [0]
    webhook_id = f"{const.DOMAIN}_{TEST_UID.replace(':', '')}_ONVIF"
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{webhook_id}", data="test_data")

    assert hass.states.is_state(entity_id, "on")
