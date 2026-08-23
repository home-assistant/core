"""Support for Overkiz (virtual) buttons."""

from dataclasses import dataclass
from typing import override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam
from pyoverkiz.models import SupportedAlias
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
from .const import IGNORED_OVERKIZ_DEVICES, LOGGER
from .coordinator import OverkizDataUpdateCoordinator
from .entity import OverkizDescriptiveEntity, OverkizEntity


@dataclass(frozen=True)
class OverkizButtonDescription(ButtonEntityDescription):
    """Class to describe an Overkiz button."""

    press_args: list[OverkizStateType] | None = None


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
    # DimmerOnOffLight (rts:DimmableLightRTSComponent)
    OverkizButtonDescription(
        key=OverkizCommand.STEP_POSITIVE,
        name="Brightness up",
        icon="mdi:brightness-7",
        # step (0-127), execution duration (0-15, optional)
        press_args=[5],
    ),
    OverkizButtonDescription(
        key=OverkizCommand.STEP_NEGATIVE,
        name="Brightness down",
        icon="mdi:brightness-3",
        # step (0-127), execution duration (0-15, optional)
        press_args=[5],
    ),
    # SmokeSensor
    OverkizButtonDescription(
        key=OverkizCommand.CHECK_EVENT_TRIGGER,
        press_args=[OverkizCommandParam.SHORT],
        name="Test",
        icon="mdi:smoke-detector",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

SUPPORTED_COMMANDS = {
    description.key: description for description in BUTTON_DESCRIPTIONS
}

ALIAS_TYPES_WITH_TRANSLATION: set[str] = {
    "favorite1",
    "ventilation",
    "partial",
    "pedestrian",
}


PARALLEL_UPDATES = 0


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
            # A device can advertise several alias ids of the same type, so let
            # pyoverkiz resolve the single one the official app would target.
            if command == OverkizCommand.GO_TO_ALIAS:
                entities.extend(
                    OverkizAliasButton(device.device_url, data.coordinator, alias)
                    for alias in device.get_most_featured_aliases().values()
                )
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
        if (press_args := self.entity_description.press_args) is not None:
            await self.executor.async_execute_command(
                self.entity_description.key, *press_args
            )
            return

        await self.executor.async_execute_command(self.entity_description.key)


class OverkizAliasButton(OverkizEntity, ButtonEntity):
    """Representation of an Overkiz goToAlias button."""

    def __init__(
        self,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
        alias: SupportedAlias,
    ) -> None:
        """Initialize the alias button."""
        super().__init__(device_url, coordinator)
        self._alias = alias
        # Keyed on the type rather than the id, since the resolved id can change
        # when the device changes the features it advertises per alias.
        self._attr_unique_id = (
            f"{self.device_url}-{OverkizCommand.GO_TO_ALIAS}_{alias.type}"
        )

        if alias.type in ALIAS_TYPES_WITH_TRANSLATION:
            self._attr_translation_key = f"go_to_alias_{alias.type}"
        else:
            LOGGER.warning(
                "Unsupported goToAlias type %s (%s) has been returned for %s",
                alias.type,
                alias.id,
                device_url,
            )
            self._attr_name = f"{alias.type.capitalize()} position"
            self._attr_icon = "mdi:star"

    @override
    async def async_press(self) -> None:
        """Handle the button press."""
        await self.executor.async_execute_command(
            OverkizCommand.GO_TO_ALIAS, self._alias.id
        )
