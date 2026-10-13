"""Binary sensor platform for the Ouman EH-800 integration."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OumanDevice
from .coordinator import OumanEh800ConfigEntry
from .entity import OumanEh800Entity, OumanEh800EntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OumanEh800BinarySensorEntityDescription(
    OumanEh800EntityDescription, BinarySensorEntityDescription
):
    """Binary sensor description with main/L1/L2 device assignment."""


SUMMER_FUNCTION_DESCRIPTION = OumanEh800BinarySensorEntityDescription(
    device=OumanDevice.L1,
    key="summer_function",
    translation_key="summer_function",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OumanEh800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ouman EH-800 binary sensors based on a config entry."""
    async_add_entities(
        [
            OumanEh800SummerFunctionBinarySensor(
                entry.runtime_data, SUMMER_FUNCTION_DESCRIPTION
            )
        ]
    )


class OumanEh800SummerFunctionBinarySensor(OumanEh800Entity, BinarySensorEntity):
    """Reports whether the summer function is holding the L1 valve closed."""

    entity_description: OumanEh800BinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return True when the summer function is active."""
        return self.coordinator.data.l1_summer_function_active
