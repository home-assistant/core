"""Tests for Kaleidescape event platform."""

import asyncio
import re
from unittest.mock import MagicMock

from kaleidescape import const as kaleidescape_const
import pytest

from homeassistant.components.kaleidescape import event
from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_LEVEL
from homeassistant.const import CONF_COMMAND, CONF_PARAMS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL, find_event_update_callback


@pytest.mark.usefixtures("mock_integration")
async def test_handle_user_defined_volume_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
) -> None:
    """Verify volume query events update the event entity timestamp."""
    update_callback = find_event_update_callback(
        mock_device.dispatcher.connect, event.EVENT_VOLUME_QUERY
    )
    entity_id = entity_registry.async_get_entity_id(
        "event", "kaleidescape", f"{MOCK_SERIAL}-volume_query"
    )
    assert entity_id is not None

    # Test initial state
    entity = hass.states.get(entity_id)
    entry = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.state == "unknown"
    assert entry
    assert entry.has_entity_name is True
    assert entry.translation_key == event.EVENT_VOLUME_QUERY
    assert entry.unique_id == f"{MOCK_SERIAL}-volume_query"

    # Test event handling
    update_callback(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert re.match(r"^\d{4}-", entity.state)
    last_updated = entity.state

    # Test repeated event updates timestamp
    await asyncio.sleep(0.01)
    update_callback(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(entity_id)
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
    """Verify volume set events expose parsed volume level and debounce behavior."""
    monkeypatch.setattr(event, "DEBOUNCE_TIME", 0)
    update_callback = find_event_update_callback(
        mock_device.dispatcher.connect, event.EVENT_VOLUME_SET
    )
    entity_id = entity_registry.async_get_entity_id(
        "event", "kaleidescape", f"{MOCK_SERIAL}-volume_set"
    )
    assert entity_id is not None

    # Test initial state
    entity = hass.states.get(entity_id)
    entry = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.state == "unknown"
    assert entry
    assert entry.has_entity_name is True
    assert entry.translation_key == event.EVENT_VOLUME_SET
    assert entry.unique_id == f"{MOCK_SERIAL}-volume_set"

    # Test event handling
    update_callback(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL, "42"],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert re.match(r"^\d{4}-", entity.state) is not None
    assert ATTR_MEDIA_VOLUME_LEVEL in entity.attributes
    assert entity.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.42
    last_updated = entity.state

    # Test with bad volume level
    update_callback(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL, "bad"],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == last_updated

    # Test debounce clears (for complete code coverage)
    monkeypatch.setattr(event, "DEBOUNCE_TIME", 1.0)
    for _ in range(2):
        update_callback(
            kaleidescape_const.USER_DEFINED_EVENT,
            [kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL, "42"],
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0)


@pytest.mark.usefixtures("mock_integration")
async def test_handle_user_defined_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
) -> None:
    """Verify user-defined events expose command/params and ignore volume commands."""
    update_callback = find_event_update_callback(
        mock_device.dispatcher.connect, event.EVENT_USER_DEFINED
    )
    entity_id = entity_registry.async_get_entity_id(
        "event", "kaleidescape", f"{MOCK_SERIAL}-user_defined"
    )
    assert entity_id is not None

    # Test initial state
    entity = hass.states.get(entity_id)
    entry = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.state == "unknown"
    assert entry
    assert entry.has_entity_name is True
    assert entry.translation_key == event.EVENT_USER_DEFINED
    assert entry.unique_id == f"{MOCK_SERIAL}-user_defined"

    # Test event handling
    update_callback(kaleidescape_const.USER_DEFINED_EVENT, ["custom_event", "42"])
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert re.match(r"^\d{4}-", entity.state) is not None
    assert CONF_COMMAND in entity.attributes
    assert entity.attributes[CONF_COMMAND] == "custom_event"
    assert CONF_PARAMS in entity.attributes
    assert entity.attributes[CONF_PARAMS] == ["42"]
    last_updated = entity.state

    # Test volume commands are ignored
    update_callback(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_CAPABILITIES],
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == last_updated


@pytest.mark.usefixtures("mock_integration")
async def test_handle_user_defined_event_empty_payload_ignored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
) -> None:
    """Test invalid/unsupported payloads are ignored."""
    update_callback = find_event_update_callback(
        mock_device.dispatcher.connect, event.EVENT_USER_DEFINED
    )
    entity_id = entity_registry.async_get_entity_id(
        "event", "kaleidescape", f"{MOCK_SERIAL}-user_defined"
    )
    assert entity_id is not None

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "unknown"

    update_callback("not_user_defined_event", [])
    await hass.async_block_till_done()
    await asyncio.sleep(0)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "unknown"

    update_callback(kaleidescape_const.USER_DEFINED_EVENT, [])
    await hass.async_block_till_done()
    await asyncio.sleep(0)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "unknown"
