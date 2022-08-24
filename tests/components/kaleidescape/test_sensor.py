"""Tests for Kaleidescape sensor platform."""

from unittest.mock import MagicMock

from kaleidescape import const as kaleidescape_const

from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL

from tests.common import MockConfigEntry

ENTITY_ID = f"sensor.kaleidescape_device_{MOCK_SERIAL}"
FRIENDLY_NAME = f"Kaleidescape Device {MOCK_SERIAL}"


async def test_sensors(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test sensors."""
    entity = hass.states.get(f"{ENTITY_ID}_media_location")
    entry = er.async_get(hass).async_get(f"{ENTITY_ID}_media_location")
    assert entity
    assert entity.state == "none"
    assert (
        entity.attributes.get(ATTR_FRIENDLY_NAME) == f"{FRIENDLY_NAME} Media Location"
    )
    assert entry
    assert entry.unique_id == f"{MOCK_SERIAL}-media_location"

    entity = hass.states.get(f"{ENTITY_ID}_play_status")
    entry = er.async_get(hass).async_get(f"{ENTITY_ID}_play_status")
    assert entity
    assert entity.state == "none"
    assert entity.attributes.get(ATTR_FRIENDLY_NAME) == f"{FRIENDLY_NAME} Play Status"
    assert entry
    assert entry.unique_id == f"{MOCK_SERIAL}-play_status"

    mock_device.movie.play_status = kaleidescape_const.PLAY_STATUS_PLAYING
    mock_device.dispatcher.send(kaleidescape_const.PLAY_STATUS)
    await hass.async_block_till_done()
    entity = hass.states.get(f"{ENTITY_ID}_play_status")
    assert entity is not None
    assert entity.state == "playing"
