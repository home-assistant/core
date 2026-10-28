"""Tests for the iCloud button platform."""

from collections.abc import Awaitable, Callable

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import MagicMock

from homeassistant.components.icloud.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEVICE

PLAY_SOUND_UNIQUE_ID = "device1_play_sound"


async def test_play_sound_button_added_for_sound_capable_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """A play sound button is added for devices that support sound."""
    icloud_service.devices.add({**DEVICE, "features": {"SND": True}})

    await setup_entry(Platform.BUTTON)

    assert (
        entity_registry.async_get_entity_id("button", DOMAIN, PLAY_SOUND_UNIQUE_ID)
        is not None
    )


async def test_play_sound_button_not_added_without_sound(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """No play sound button is added for devices that cannot play sound."""
    icloud_service.devices.add({**DEVICE, "features": {"SND": False}})

    await setup_entry(Platform.BUTTON)

    assert (
        entity_registry.async_get_entity_id("button", DOMAIN, PLAY_SOUND_UNIQUE_ID)
        is None
    )


async def test_play_sound_button_press_plays_sound(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """Pressing the button plays the sound on the device."""
    apple_device = icloud_service.devices.add({**DEVICE, "features": {"SND": True}})

    await setup_entry(Platform.BUTTON)

    entity_id = entity_registry.async_get_entity_id(
        "button", DOMAIN, PLAY_SOUND_UNIQUE_ID
    )
    assert entity_id is not None

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )

    apple_device.play_sound.assert_called_once_with()


async def test_play_sound_button_added_when_device_appears_later(
    hass: HomeAssistant,
    devices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """A device discovered after setup gets a play sound button."""
    icloud_service.devices.add({**DEVICE, "features": {"SND": False}})

    await setup_entry(Platform.BUTTON)

    assert (
        entity_registry.async_get_entity_id("button", DOMAIN, PLAY_SOUND_UNIQUE_ID)
        is None
    )

    icloud_service.devices.add(
        {**DEVICE, "id": "device2", "name": "iPad", "features": {"SND": True}}
    )
    await hass.async_add_executor_job(devices_config_entry.runtime_data.update_devices)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id("button", DOMAIN, "device2_play_sound")
        is not None
    )
