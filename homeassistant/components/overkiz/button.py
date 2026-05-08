"""Support for Overkiz (virtual) buttons."""

from dataclasses import dataclass
from typing import cast, override

from pyoverkiz.enums import OverkizAttribute, OverkizCommand, OverkizCommandParam
from pyoverkiz.types import StateType as OverkizStateType

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OverkizDataConfigEntry
from .const import IGNORED_OVERKIZ_DEVICES
from .coordinator import OverkizDataUpdateCoordinator
from .entity import OverkizDescriptiveEntity, OverkizEntity


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
        # startIdentify and identify are reversed... Swap this when fixed in API.
        key=OverkizCommand.IDENTIFY,
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
        # startIdentify and identify are reversed... Swap this when fixed in API.
        key=OverkizCommand.START_IDENTIFY,
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

ALIAS_TYPES_WITH_TRANSLATION: set[str] = {"favorite1", "ventilation", "partial"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

        for command in device.definition.commands:
            # Dynamically generate buttons for goToAlias commands based on the supported aliases of the device
            if command == OverkizCommand.GO_TO_ALIAS:
                if attribute := device.attributes.get(
                    OverkizAttribute.CORE_SUPPORTED_ALIASES
                ):
                    entities.extend(
                        OverkizAliasButton(
                            device.device_url,
                            data.coordinator,
                            alias_id=str(alias["id"]),
                            alias_type=alias.get("type", ""),
                        )
                        for alias in cast(list, attribute.value)
                    )
            # Create buttons for supported commands based on the predefined BUTTON_DESCRIPTIONS
            elif description := SUPPORTED_COMMANDS.get(command):
                entities.append(
                    OverkizButton(device.device_url, data.coordinator, description)
                )

    async_add_entities(entities)


class OverkizButton(OverkizDescriptiveEntity, ButtonEntity):
    """Representation of an Overkiz Button."""

    entity_description: OverkizButtonDescription

    @override
    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.press_args:
            await self.executor.async_execute_command(
                self.entity_description.key, self.entity_description.press_args
            )
            return

        await self.executor.async_execute_command(self.entity_description.key)


class OverkizAliasButton(OverkizEntity, ButtonEntity):
    """Representation of an Overkiz goToAlias button."""

    _attr_icon = "mdi:star"

    def __init__(
        self,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
        alias_id: str,
        alias_type: str,
    ) -> None:
        """Initialize the alias button."""
        super().__init__(device_url, coordinator)
        self._alias_id = alias_id
        if alias_type in ALIAS_TYPES_WITH_TRANSLATION:
            self._attr_translation_key = f"go_to_alias_{alias_type}"
        else:
            self._attr_name = f"{alias_type.capitalize()} position"
        self._attr_unique_id = (
            f"{self.device_url}-{OverkizCommand.GO_TO_ALIAS}_{alias_id}"
        )

    @override
    async def async_press(self) -> None:
        """Handle the button press."""
        await self.executor.async_execute_command(
            OverkizCommand.GO_TO_ALIAS, self._alias_id
        )
