"""Test the UniFi Protect button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from pyunifiprotect.data.devices import Camera, Chime, Doorlock

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    enable_entity,
    init_entry,
    remove_entities,
)


async def test_button_chime_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, chime: Chime
) -> None:
    """Test removing and re-adding a light device."""

    await init_entry(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 4, 2)
    await remove_entities(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 0, 0)
    await adopt_devices(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 4, 2)


async def test_reboot_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
) -> None:
    """Test button entity."""

    await init_entry(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 4, 2)

    ufp.api.reboot_device = AsyncMock()

    unique_id = f"{chime.mac}_reboot"
    entity_id = "button.test_chime_reboot_device"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    ufp.api.reboot_device.assert_called_once()


async def test_chime_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
) -> None:
    """Test button entity."""

    await init_entry(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 4, 2)

    ufp.api.play_speaker = AsyncMock()

    unique_id = f"{chime.mac}_play"
    entity_id = "button.test_chime_play_chime"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    ufp.api.play_speaker.assert_called_once()


async def test_adopt_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    doorbell: Camera,
) -> None:
    """Test button entity."""

    doorlock._api = ufp.api
    doorlock.is_adopted = False
    doorlock.can_adopt = True

    await init_entry(hass, ufp, [])

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = None
    mock_msg.new_obj = doorlock
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BUTTON, 1, 1)

    ufp.api.adopt_device = AsyncMock()

    unique_id = f"{doorlock.mac}_adopt"
    entity_id = "button.test_lock_adopt_device"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    ufp.api.adopt_device.assert_called_once()


async def test_adopt_button_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    doorbell: Camera,
) -> None:
    """Test button entity."""

    entity_id = "button.test_lock_adopt_device"

    doorlock._api = ufp.api
    doorlock.is_adopted = False
    doorlock.can_adopt = True

    await init_entry(hass, ufp, [doorlock])
    assert_entity_counts(hass, Platform.BUTTON, 1, 1)
    entity = entity_registry.async_get(entity_id)
    assert entity

    await adopt_devices(hass, ufp, [doorlock], fully_adopt=True)
    assert_entity_counts(hass, Platform.BUTTON, 2, 0)
    entity = entity_registry.async_get(entity_id)
    assert entity is None
