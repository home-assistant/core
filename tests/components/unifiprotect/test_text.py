"""Test the UniFi Protect text platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from pyunifiprotect.data import Camera, DoorbellMessageType, LCDMessage

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.text import CAMERA
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    ids_from_device_description,
    init_entry,
    remove_entities,
)


async def test_text_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.TEXT, 1, 1)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.TEXT, 0, 0)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.TEXT, 1, 1)


async def test_text_camera_setup(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test text entity setup for camera devices."""

    doorbell.lcd_message = LCDMessage(
        type=DoorbellMessageType.CUSTOM_MESSAGE, text="Test"
    )
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.TEXT, 1, 1)

    entity_registry = er.async_get(hass)

    description = CAMERA[0]
    unique_id, entity_id = ids_from_device_description(
        Platform.TEXT, doorbell, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Test"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_text_camera_set(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test text entity setting value camera devices."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.TEXT, 1, 1)

    description = CAMERA[0]
    unique_id, entity_id = ids_from_device_description(
        Platform.TEXT, doorbell, description
    )

    doorbell.__fields__["set_lcd_text"] = Mock(final=False)
    doorbell.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "text",
        "set_value",
        {ATTR_ENTITY_ID: entity_id, "value": "Test test"},
        blocking=True,
    )

    doorbell.set_lcd_text.assert_called_once_with(
        DoorbellMessageType.CUSTOM_MESSAGE, text="Test test"
    )
