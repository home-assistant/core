"""Tests for the diagnostics data provided by the Denon AVR integration."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.denonavr.const import (
    CONF_MANUFACTURER,
    CONF_SERIAL_NUMBER,
    CONF_USE_TELNET,
    CONF_ZONE2,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_TYPE
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_MANUFACTURER,
    TEST_MODEL,
    TEST_RECEIVER_TYPE,
    TEST_SERIALNUMBER,
)


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    client.receiver_port = 8080
    client.telnet_available = True
    client.telnet_connected = True
    client.telnet_healthy = True
    client.power = "ON"
    client.state = "on"
    client.muted = False
    client.volume = -35.5
    client.input_func = "CD"
    client.input_func_list = ["CD", "TV Audio", "Spotify"]
    client.netaudio_func_list = ["Spotify"]
    client.playing_func_list = ["Spotify"]
    client.support_sound_mode = True
    client.sound_mode = "STEREO"
    client.sound_mode_raw = "Stereo"
    client.sound_mode_list = ["MUSIC", "MOVIE", "STEREO"]
    client.support_tone_control = True
    client.dynamic_eq = True
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_MODEL}-{TEST_SERIALNUMBER}",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_MODEL: TEST_MODEL,
            CONF_TYPE: TEST_RECEIVER_TYPE,
            CONF_MANUFACTURER: TEST_MANUFACTURER,
            CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
        },
        options={CONF_USE_TELNET: True, CONF_ZONE2: False},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
