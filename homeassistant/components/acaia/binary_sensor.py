"""Binary sensor platform for acaia scales."""

from collections.abc import Callable
from dataclasses import dataclass

from pyacaia_async.acaiascale import AcaiaScale

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AcaiaConfigEntry
from .entity import AcaiaEntity, AcaiaEntityDescription


@dataclass(kw_only=True, frozen=True)
class AcaiaBinarySensorEntityDescription(
    AcaiaEntityDescription, BinarySensorEntityDescription
):
    """Description for Acaia Binary Sensor entities."""

    is_on_fn: Callable[[AcaiaScale], bool]


BINARY_SENSORS: tuple[AcaiaBinarySensorEntityDescription, ...] = (
    AcaiaBinarySensorEntityDescription(
        key="timer_running",
        translation_key="timer_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda scale: scale.timer_running,
    ),
    AcaiaBinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda scale: scale.connected,
        available_fn=lambda _: True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AcaiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities and services."""

    coordinator = entry.runtime_data
    async_add_entities(
        [AcaiaSensor(coordinator, description) for description in BINARY_SENSORS]
    )


class AcaiaSensor(AcaiaEntity, BinarySensorEntity):
    """Representation of a Acaia Binary Sensor."""

    entity_description: AcaiaBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._scale)
