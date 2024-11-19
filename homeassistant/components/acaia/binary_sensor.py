"""Binary sensor platform for Acaia scales."""

from collections.abc import Callable
from dataclasses import dataclass

from aioacaia.acaiascale import AcaiaScale

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AcaiaConfigEntry
from .entity import AcaiaEntity


@dataclass(kw_only=True, frozen=True)
class AcaiaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description for Acaia binary sensor entities."""

    is_on_fn: Callable[[AcaiaScale], bool]


BINARY_SENSORS: tuple[AcaiaBinarySensorEntityDescription, ...] = (
    AcaiaBinarySensorEntityDescription(
        key="timer_running",
        translation_key="timer_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda scale: scale.timer_running,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AcaiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""

    coordinator = entry.runtime_data
    async_add_entities(
        AcaiaBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class AcaiaBinarySensor(AcaiaEntity, BinarySensorEntity):
    """Representation of an Acaia binary sensor."""

    entity_description: AcaiaBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._scale)
