"""Support for Electric Kiwi sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from electrickiwi_api.model import Hop

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN
from .coordinator import ElectricKiwiHOPDataCoordinator

_LOGGER = logging.getLogger(DOMAIN)

ATTR_EK_HOP_START = "hop_sensor_start"
ATTR_EK_HOP_END = "hop_sensor_end"


@dataclass
class ElectricKiwiHOPRequiredKeysMixin:
    """Mixin for required HOP keys."""

    value_func: Callable[[Hop], datetime]


@dataclass
class ElectricKiwiHOPSensorEntityDescription(
    SensorEntityDescription,
    ElectricKiwiHOPRequiredKeysMixin,
):
    """Describes Electric Kiwi HOP sensor entity."""


def _check_and_move_time(hop: Hop, time: str) -> datetime:
    """Return the time a day forward if HOP end_time is in the past."""
    date_time = datetime.combine(
        datetime.today(),
        datetime.strptime(time, "%I:%M %p").time(),
    ).astimezone(dt_util.DEFAULT_TIME_ZONE)

    end_time = datetime.combine(
        datetime.today(),
        datetime.strptime(hop.end.end_time, "%I:%M %p").time(),
    ).astimezone(dt_util.DEFAULT_TIME_ZONE)

    if end_time < datetime.now().astimezone(dt_util.DEFAULT_TIME_ZONE):
        return date_time + timedelta(days=1)
    return date_time


HOP_SENSOR_TYPE: tuple[ElectricKiwiHOPSensorEntityDescription, ...] = (
    ElectricKiwiHOPSensorEntityDescription(
        key=ATTR_EK_HOP_START,
        translation_key="hopfreepowerstart",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_func=lambda hop: _check_and_move_time(hop, hop.start.start_time),
    ),
    ElectricKiwiHOPSensorEntityDescription(
        key=ATTR_EK_HOP_END,
        translation_key="hopfreepowerend",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_func=lambda hop: _check_and_move_time(hop, hop.end.end_time),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Electric Kiwi Sensor Setup."""
    hop_coordinator: ElectricKiwiHOPDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    hop_entities = [
        ElectricKiwiHOPEntity(hop_coordinator, description)
        for description in HOP_SENSOR_TYPE
    ]
    async_add_entities(hop_entities)


class ElectricKiwiHOPEntity(
    CoordinatorEntity[ElectricKiwiHOPDataCoordinator], SensorEntity
):
    """Entity object for Electric Kiwi sensor."""

    entity_description: ElectricKiwiHOPSensorEntityDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        hop_coordinator: ElectricKiwiHOPDataCoordinator,
        description: ElectricKiwiHOPSensorEntityDescription,
    ) -> None:
        """Entity object for Electric Kiwi sensor."""
        super().__init__(hop_coordinator)

        self._attr_unique_id = f"{self.coordinator._ek_api.customer_number}_{self.coordinator._ek_api.connection_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self.coordinator.data)
