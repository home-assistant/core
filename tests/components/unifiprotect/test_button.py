"""Test the UniFi Protect button platform."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock

from pyunifiprotect.data.devices import Chime

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import MockUFPFixture, assert_entity_counts, enable_entity, init_entry


async def test_reboot_button(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    chime: Chime,
):
    """Test button entity."""

    await init_entry(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 3, 2)

    ufp.api.reboot_device = AsyncMock()

    unique_id = f"{chime.mac}_reboot"
    entity_id = "button.test_chime_reboot_device"

    entity_registry = er.async_get(hass)
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
    ufp: MockUFPFixture,
    chime: Chime,
):
    """Test button entity."""

    await init_entry(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 3, 2)

    ufp.api.play_speaker = AsyncMock()

    unique_id = f"{chime.mac}_play"
    entity_id = "button.test_chime_play_chime"

    entity_registry = er.async_get(hass)
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
