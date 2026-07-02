"""Binary sensor platform for KEBA P40."""

from collections.abc import Callable
from dataclasses import dataclass

from keba_kecontact_p40 import Wallbox

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import KebaP40ConfigEntry
from .entity import KebaP40Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KebaP40BinarySensorDescription(BinarySensorEntityDescription):
    """Describes a KEBA P40 binary sensor."""

    value_fn: Callable[[Wallbox], bool | None]


BINARY_SENSORS: tuple[KebaP40BinarySensorDescription, ...] = (
    KebaP40BinarySensorDescription(
        key="vehicle_plugged",
        translation_key="vehicle_plugged",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda wb: wb.vehicle_plugged,
    ),
    KebaP40BinarySensorDescription(
        key="session_active",
        translation_key="session_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda wb: wb.session_active,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaP40ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA P40 binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        KebaP40BinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class KebaP40BinarySensor(KebaP40Entity, BinarySensorEntity):
    """A KEBA P40 binary sensor."""

    entity_description: KebaP40BinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        return self.entity_description.value_fn(self._wallbox)
