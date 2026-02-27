"""Tests for Trinnov Altitude sensor platform."""

from homeassistant.core import HomeAssistant

from . import MOCK_ID

from tests.common import MockConfigEntry

POWER_ENTITY_ID = f"sensor.trinnov_altitude_{MOCK_ID}_power_status"
CONNECTION_ENTITY_ID = f"sensor.trinnov_altitude_{MOCK_ID}_connection_status"
SYNC_ENTITY_ID = f"sensor.trinnov_altitude_{MOCK_ID}_sync_status"
DECODER_ENTITY_ID = f"sensor.trinnov_altitude_{MOCK_ID}_decoder"
SOURCE_FORMAT_ENTITY_ID = f"sensor.trinnov_altitude_{MOCK_ID}_source_format"
AUDIOSYNC_ENTITY_ID = f"sensor.trinnov_altitude_{MOCK_ID}_audiosync"


async def test_entities_and_values(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test sensor entities and default values."""
    assert hass.states.get(POWER_ENTITY_ID).state == "ready"
    assert hass.states.get(CONNECTION_ENTITY_ID).state == "connected"
    assert hass.states.get(SYNC_ENTITY_ID).state == "synced"
    assert hass.states.get(DECODER_ENTITY_ID).state == "Dolby Atmos"
    assert hass.states.get(SOURCE_FORMAT_ENTITY_ID).state == "PCM"
    assert hass.states.get(AUDIOSYNC_ENTITY_ID).state == "42"


async def test_power_and_connection_when_disconnected(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test sensor values when device is disconnected."""
    mock_device.connected = False
    mock_device.state.synced = False

    callback = mock_device.register_callback.call_args[0][0]
    callback("received_message", None)
    await hass.async_block_till_done()

    assert hass.states.get(POWER_ENTITY_ID).state == "off"
    assert hass.states.get(CONNECTION_ENTITY_ID).state == "disconnected"
    assert hass.states.get(SYNC_ENTITY_ID).state == "syncing"
