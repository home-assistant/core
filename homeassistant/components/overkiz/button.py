"""Support for Overkiz (virtual) buttons."""

from __future__ import annotations

from dataclasses import dataclass

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam
from pyoverkiz.types import StateType as OverkizStateType

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OverkizDataConfigEntry
from .const import IGNORED_OVERKIZ_DEVICES
from .entity import OverkizDescriptiveEntity


@dataclass(frozen=True)
class OverkizButtonDescription(ButtonEntityDescription):
    """Class to describe an Overkiz button."""

    press_args: OverkizStateType | None = None


BUTTON_DESCRIPTIONS: list[OverkizButtonDescription] = [
    # My Position (cover, light)
    OverkizButtonDescription(
        key=OverkizCommand.MY,
        name="My position",
        icon="mdi:star",
    ),
    # Identify
    OverkizButtonDescription(
        key=OverkizCommand.IDENTIFY,  # startIdentify and identify are reversed... Swap this when fixed in API.
        name="Start identify",
        icon="mdi:human-greeting-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    OverkizButtonDescription(
        key=OverkizCommand.STOP_IDENTIFY,
        name="Stop identify",
        icon="mdi:human-greeting-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    OverkizButtonDescription(
        key=OverkizCommand.START_IDENTIFY,  # startIdentify and identify are reversed... Swap this when fixed in API.
        name="Identify",
        icon="mdi:human-greeting-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=ButtonDeviceClass.IDENTIFY,
    ),
    # RTDIndoorSiren / RTDOutdoorSiren
    OverkizButtonDescription(
        key=OverkizCommand.DING_DONG, name="Ding dong", icon="mdi:bell-ring"
    ),
    OverkizButtonDescription(key=OverkizCommand.BIP, name="Bip", icon="mdi:bell-ring"),
    OverkizButtonDescription(
        key=OverkizCommand.FAST_BIP_SEQUENCE,
        name="Fast bip sequence",
        icon="mdi:bell-ring",
    ),
    OverkizButtonDescription(
        key=OverkizCommand.RING, name="Ring", icon="mdi:bell-ring"
    ),
    # DynamicScreen (ogp:blind) uses goToAlias (id 1: favorite1) instead of 'my'
    OverkizButtonDescription(
        key=OverkizCommand.GO_TO_ALIAS,
        press_args="1",
        name="My position",
        icon="mdi:star",
    ),
    OverkizButtonDescription(
        key=OverkizCommand.CYCLE,
        name="Toggle",
        icon="mdi:sync",
    ),
    # SmokeSensor
    OverkizButtonDescription(
        key=OverkizCommand.CHECK_EVENT_TRIGGER,
        press_args=OverkizCommandParam.SHORT,
        name="Test",
        icon="mdi:smoke-detector",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

SUPPORTED_COMMANDS = {
    description.key: description for description in BUTTON_DESCRIPTIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz button from a config entry."""
    data = entry.runtime_data
    entities: list[ButtonEntity] = []

    for device in data.coordinator.data.values():
        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        entities.extend(
            OverkizButton(
                device.device_url,
                data.coordinator,
                description,
            )
            for command in device.definition.commands
            if (description := SUPPORTED_COMMANDS.get(command.command_name))
        )

    async_add_entities(entities)


class OverkizButton(OverkizDescriptiveEntity, ButtonEntity):
    """Representation of an Overkiz Button."""

    entity_description: OverkizButtonDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.press_args:
            await self.executor.async_execute_command(
                self.entity_description.key, self.entity_description.press_args
            )
            return

        await self.executor.async_execute_command(self.entity_description.key)
