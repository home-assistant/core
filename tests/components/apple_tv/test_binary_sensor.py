"""Tests for Apple TV binary sensor."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyatv.const import DeviceModel, KeyboardFocusState, Protocol

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from .common import create_conf, mrp_service

from tests.common import MockConfigEntry


async def test_keyboard_focus_entity_created_on_setup(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
) -> None:
    """Test the keyboard focus binary sensor is created when the device supports it.

    Regression test for https://github.com/home-assistant/core/issues/170075 — the
    initial SIGNAL_CONNECTED dispatch happens in async_first_connect (before platform
    forwarding), so the binary_sensor platform must also handle the already-connected
    case rather than relying solely on the dispatcher signal.
    """
    atv = AsyncMock()
    atv.close = MagicMock()
    atv.features = MagicMock()
    atv.features.in_state = MagicMock(return_value=True)
    atv.keyboard = AsyncMock()
    atv.keyboard.text_focus_state = KeyboardFocusState.Unfocused
    atv.push_updater = MagicMock()
    atv.device_info.model = DeviceModel.Gen4K
    atv.device_info.raw_model = "AppleTV6,2"
    atv.device_info.version = "15.0"
    atv.device_info.mac = "AA:BB:CC:DD:EE:FF"

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        unique_id="mrpid",
        data={
            CONF_ADDRESS: "127.0.0.1",
            CONF_NAME: "Living Room",
            "credentials": {str(Protocol.MRP.value): "mrp_creds"},
            "identifiers": ["mrpid"],
        },
    )
    entry.add_to_hass(hass)

    scan_result = create_conf("127.0.0.1", "Living Room", mrp_service())

    with (
        patch("homeassistant.components.apple_tv.scan", return_value=[scan_result]),
        patch("homeassistant.components.apple_tv.connect", return_value=atv),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.living_room_living_room_keyboard_focus")
    assert state is not None
