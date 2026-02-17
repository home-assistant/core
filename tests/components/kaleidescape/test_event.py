"""Tests for Kaleidescape media player platform."""

import asyncio
import re
from unittest.mock import MagicMock

from kaleidescape import const as kaleidescape_const
import pytest

from homeassistant.components.kaleidescape import event
from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_LEVEL
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_COMMAND, CONF_PARAMS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL

ENTITY_ID = f"event.kaleidescape_device_{MOCK_SERIAL}"
FRIENDLY_NAME = f"Kaleidescape Device {MOCK_SERIAL}"


@pytest.mark.usefixtures("mock_integration")
async def test_handle_user_defined_volume_event(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_device: MagicMock
) -> None:
    """Test test_handle_user_defined_volume_event callback."""

    # Test initial state
    entity = hass.states.get(f"{ENTITY_ID}_volume_state_queried")
    entry = entity_registry.async_get(f"{ENTITY_ID}_volume_state_queried")
    assert entity is not None
    assert entity.state == "unknown"
    assert (
        entity.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{FRIENDLY_NAME} Volume state queried"
    )
    assert entry
    assert entry.unique_id == f"{MOCK_SERIAL}-volume_query"

    # Test event handling
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(f"{ENTITY_ID}_volume_state_queried")
    assert entity is not None
    assert re.match(r"^\d{4}-", entity.state)
    last_updated = entity.state

    # Test repeated event updates timestamp
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(f"{ENTITY_ID}_volume_state_queried")
    assert entity is not None
    assert re.match(r"^\d{4}-", entity.state)
    assert entity.state != last_updated


@pytest.mark.usefixtures("mock_integration")
async def test_handle_user_defined_volume_set_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test test_handle_user_defined_volume_set_event callback."""
    monkeypatch.setattr(event, "DEBOUNCE_TIME", 0)

    # Test initial state
    entity = hass.states.get(f"{ENTITY_ID}_volume_level_set")
    entry = entity_registry.async_get(f"{ENTITY_ID}_volume_level_set")
    assert entity is not None
    assert entity.state == "unknown"
    assert (
        entity.attributes.get(ATTR_FRIENDLY_NAME) == f"{FRIENDLY_NAME} Volume level set"
    )
    assert entry
    assert entry.unique_id == f"{MOCK_SERIAL}-volume_set"

    # Test event handling
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL, "42"],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(f"{ENTITY_ID}_volume_level_set")
    assert entity is not None
    assert re.match(r"^\d{4}-", entity.state) is not None
    assert ATTR_MEDIA_VOLUME_LEVEL in entity.attributes
    assert entity.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.42
    last_updated = entity.state

    # Test with bad volume level
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL, "bad"],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(f"{ENTITY_ID}_volume_level_set")
    assert entity is not None
    assert entity.state == last_updated

    # Test debounce clears (for complete code coverage)
    monkeypatch.setattr(event, "DEBOUNCE_TIME", 1.0)
    for _ in range(2):
        mock_device.dispatcher.send(
            kaleidescape_const.USER_DEFINED_EVENT,
            [kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL, "42"],
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0)


@pytest.mark.usefixtures("mock_integration")
async def test_handle_user_defined_event(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_device: MagicMock
) -> None:
    """Test test_handle_user_defined_event callback."""

    # Test initial state
    entity = hass.states.get(f"{ENTITY_ID}_user_defined_event")
    entry = entity_registry.async_get(f"{ENTITY_ID}_user_defined_event")
    assert entity is not None
    assert entity.state == "unknown"
    assert (
        entity.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{FRIENDLY_NAME} User defined event"
    )
    assert entry
    assert entry.unique_id == f"{MOCK_SERIAL}-user_defined"

    # Test event handling
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT, ["custom_event", "42"]
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(f"{ENTITY_ID}_user_defined_event")
    assert entity is not None
    assert re.match(r"^\d{4}-", entity.state) is not None
    assert CONF_COMMAND in entity.attributes
    assert entity.attributes[CONF_COMMAND] == "custom_event"
    assert CONF_PARAMS in entity.attributes
    assert entity.attributes[CONF_PARAMS] == ["42"]
    last_updated = entity.state

    # Test volume commands are ignored
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_CAPABILITIES],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(f"{ENTITY_ID}_user_defined_event")
    assert entity is not None
    assert entity.state == last_updated
