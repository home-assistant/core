"""Binary sensors for the status flags of the air conditioner behind a gateway."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, override

from intesis_gw_modbus import IntesisSingleUnitGateway

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IntesisConfigEntry, IntesisUnitCoordinator
from .entity import IntesisEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IntesisBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A status flag, and where to read it off the gateway."""

    report_name: str
    value_fn: Callable[[IntesisSingleUnitGateway], bool | None]


BINARY_SENSORS: Final[tuple[IntesisBinarySensorEntityDescription, ...]] = (
    IntesisBinarySensorEntityDescription(
        key="alarm",
        translation_key="alarm",
        report_name="control",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.alarm,
    ),
    IntesisBinarySensorEntityDescription(
        key="window_open",
        report_name="window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda device: device.window_open,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntesisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors of the air conditioner behind the gateway."""
    async_add_entities(
        IntesisBinarySensor(entry.runtime_data.unit, description)
        for description in BINARY_SENSORS
    )


class IntesisBinarySensor(IntesisEntity, BinarySensorEntity):
    """A status flag of the air conditioner behind an Intesis gateway."""

    entity_description: IntesisBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IntesisUnitCoordinator,
        description: IntesisBinarySensorEntityDescription,
    ) -> None:
        """Bind to the flag the description reads."""
        super().__init__(coordinator, description.key, description.report_name)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """The flag as the gateway reported it in the most recent poll."""
        return self.entity_description.value_fn(self.coordinator.device)
