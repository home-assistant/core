"""Support for Overkiz (virtual) buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN, IGNORED_OVERKIZ_DEVICES
from .entity import OverkizDescriptiveEntity

BUTTON_DESCRIPTIONS: list[ButtonEntityDescription] = [
    # My Position (cover, light)
    ButtonEntityDescription(
        key="my",
        name="My Position",
        icon="mdi:star",
    ),
    # Identify
    ButtonEntityDescription(
        key="identify",  # startIdentify and identify are reversed... Swap this when fixed in API.
        name="Start Identify",
        icon="mdi:human-greeting-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ButtonEntityDescription(
        key="stopIdentify",
        name="Stop Identify",
        icon="mdi:human-greeting-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ButtonEntityDescription(
        key="startIdentify",  # startIdentify and identify are reversed... Swap this when fixed in API.
        name="Identify",
        icon="mdi:human-greeting-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # RTDIndoorSiren / RTDOutdoorSiren
    ButtonEntityDescription(key="dingDong", name="Ding Dong", icon="mdi:bell-ring"),
    ButtonEntityDescription(key="bip", name="Bip", icon="mdi:bell-ring"),
    ButtonEntityDescription(
        key="fastBipSequence", name="Fast Bip Sequence", icon="mdi:bell-ring"
    ),
    ButtonEntityDescription(key="ring", name="Ring", icon="mdi:bell-ring"),
]

SUPPORTED_COMMANDS = {
    description.key: description for description in BUTTON_DESCRIPTIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz button from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = []

    for device in data.coordinator.data.values():
        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        for command in device.definition.commands:
            if description := SUPPORTED_COMMANDS.get(command.command_name):
                entities.append(
                    OverkizButton(
                        device.device_url,
                        data.coordinator,
                        description,
                    )
                )

    async_add_entities(entities)


class OverkizButton(OverkizDescriptiveEntity, ButtonEntity):
    """Representation of an Overkiz Button."""

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.executor.async_execute_command(self.entity_description.key)
