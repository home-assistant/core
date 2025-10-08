"""Test the Reolink binary sensor platform."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from .conftest import TEST_CAM_NAME, TEST_DUO_MODEL, TEST_HOST_MODEL

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


async def test_motion_sensor(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test binary sensor entity with motion sensor."""
    reolink_host.model = TEST_DUO_MODEL
    reolink_host.motion_detected.return_value = True
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_CAM_NAME}_motion_lens_0"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_host.motion_detected.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    # test ONVIF webhook callback
    reolink_host.motion_detected.return_value = True
    reolink_host.ONVIF_event_callback.return_value = [0]
    webhook_id = config_entry.runtime_data.host.webhook_id
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{webhook_id}", data="test_data")

    assert hass.states.get(entity_id).state == STATE_ON


async def test_smart_ai_sensor(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test smart ai binary sensor entity."""
    reolink_host.model = TEST_HOST_MODEL
    reolink_host.baichuan.smart_ai_state.return_value = True
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_CAM_NAME}_crossline_zone1_person"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_host.baichuan.smart_ai_state.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_tcp_callback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test tcp callback using motion sensor."""

    class callback_mock_class:
        callback_func = None

        def register_callback(
            self, callback_id: str, callback: Callable[[], None], *args, **key_args
        ) -> None:
            if callback_id.endswith("_motion"):
                self.callback_func = callback

    callback_mock = callback_mock_class()

    reolink_host.model = TEST_HOST_MODEL
    reolink_host.baichuan.events_active = True
    reolink_host.baichuan.subscribe_events.reset_mock(side_effect=True)
    reolink_host.baichuan.register_callback = callback_mock.register_callback
    reolink_host.motion_detected.return_value = True

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_CAM_NAME}_motion"
    assert hass.states.get(entity_id).state == STATE_ON

    # simulate a TCP push callback
    reolink_host.motion_detected.return_value = False
    assert callback_mock.callback_func is not None
    callback_mock.callback_func()

    assert hass.states.get(entity_id).state == STATE_OFF
