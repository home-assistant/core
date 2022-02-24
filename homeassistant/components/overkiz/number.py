"""Support for Overkiz (virtual) numbers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pyoverkiz.enums import OverkizCommand, OverkizState

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN, IGNORED_OVERKIZ_DEVICES
from .entity import OverkizDescriptiveEntity


@dataclass
class OverkizNumberDescriptionMixin:
    """Define an entity description mixin for number entities."""

    command: str


@dataclass
class OverkizNumberDescription(NumberEntityDescription, OverkizNumberDescriptionMixin):
    """Class to describe an Overkiz number."""


NUMBER_DESCRIPTIONS: list[OverkizNumberDescription] = [
    # Cover: My Position (0 - 100)
    OverkizNumberDescription(
        key=OverkizState.CORE_MEMORIZED_1_POSITION,
        name="My Position",
        icon="mdi:content-save-cog",
        command=OverkizCommand.SET_MEMORIZED_1_POSITION,
        entity_category=EntityCategory.CONFIG,
    ),
    # WaterHeater: Expected Number Of Shower (2 - 4)
    OverkizNumberDescription(
        key=OverkizState.CORE_EXPECTED_NUMBER_OF_SHOWER,
        name="Expected Number Of Shower",
        icon="mdi:shower-head",
        command=OverkizCommand.SET_EXPECTED_NUMBER_OF_SHOWER,
        min_value=2,
        max_value=4,
        entity_category=EntityCategory.CONFIG,
    ),
    # SomfyHeatingTemperatureInterface
    OverkizNumberDescription(
        key=OverkizState.CORE_ECO_ROOM_TEMPERATURE,
        name="Eco Room Temperature",
        icon="mdi:thermometer",
        command=OverkizCommand.SET_ECO_TEMPERATURE,
        min_value=6,
        max_value=29,
        entity_category=EntityCategory.CONFIG,
    ),
    OverkizNumberDescription(
        key=OverkizState.CORE_COMFORT_ROOM_TEMPERATURE,
        name="Comfort Room Temperature",
        icon="mdi:home-thermometer-outline",
        command=OverkizCommand.SET_COMFORT_TEMPERATURE,
        min_value=7,
        max_value=30,
        entity_category=EntityCategory.CONFIG,
    ),
    OverkizNumberDescription(
        key=OverkizState.CORE_SECURED_POSITION_TEMPERATURE,
        name="Freeze Protection Temperature",
        icon="mdi:sun-thermometer-outline",
        command=OverkizCommand.SET_SECURED_POSITION_TEMPERATURE,
        min_value=5,
        max_value=15,
        entity_category=EntityCategory.CONFIG,
    ),
]

SUPPORTED_STATES = {description.key: description for description in NUMBER_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz number from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    entities: list[OverkizNumber] = []

    for device in data.coordinator.data.values():
        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        for state in device.definition.states:
            if description := SUPPORTED_STATES.get(state.qualified_name):
                entities.append(
                    OverkizNumber(
                        device.device_url,
                        data.coordinator,
                        description,
                    )
                )

    async_add_entities(entities)


class OverkizNumber(OverkizDescriptiveEntity, NumberEntity):
    """Representation of an Overkiz Number."""

    entity_description: OverkizNumberDescription

    @property
    def value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if state := self.device.states.get(self.entity_description.key):
            return cast(float, state.value)

        return None

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        await self.executor.async_execute_command(
            self.entity_description.command, value
        )
