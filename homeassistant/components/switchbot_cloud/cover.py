"""Support for the Switchbot Bot as a Cover."""

from switchbot_api import Device, Remote, SwitchBotAPI

from homeassistant.components.cover import CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import DOMAIN
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        SwitchBotCloudCover(data.api, device, coordinator)
        for device, coordinator in data.devices.buttons
    )


class SwitchBotCloudCover(SwitchBotCloudEntity, CoverEntity):
    """Representation of a SwitchBot Cover."""

    _attr_name = None


async def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudCover:
    """Make a Cover Device."""
    return SwitchBotCloudCover(api, device, coordinator)
