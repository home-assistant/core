"""The lookin integration sensor platform."""
from __future__ import annotations

import logging

from aiolookin import MeteoSensor, SensorID

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import LookinDeviceEntity
from .models import LookinData

LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lookin sensors from the config entry."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [LookinSensorEntity(description, lookin_data) for description in SENSOR_TYPES]
    )


class LookinSensorEntity(CoordinatorEntity, LookinDeviceEntity, SensorEntity, Entity):
    """A lookin device sensor entity."""

    def __init__(
        self, description: SensorEntityDescription, lookin_data: LookinData
    ) -> None:
        """Init the lookin sensor entity."""
        super().__init__(lookin_data.meteo_coordinator)
        LookinDeviceEntity.__init__(self, lookin_data)
        self.entity_description = description
        self._attr_name = f"{self._lookin_device.name} {description.name}"
        self._attr_native_value = getattr(self.coordinator.data, description.key)
        self._attr_unique_id = f"{self._lookin_device.id}-{description.key}"

    def _handle_coordinator_update(self) -> None:
        """Update the state of the entity."""
        self._attr_native_value = getattr(
            self.coordinator.data, self.entity_description.key
        )
        super()._handle_coordinator_update()

    @callback
    def _async_push_update(self, msg: dict[str, str]) -> None:
        """Process an update pushed via UDP."""
        if int(msg["event_id"]):
            return
        LOGGER.debug("Processing push message for meteo sensor: %s", msg)
        meteo: MeteoSensor = self.coordinator.data
        meteo.update_from_value(msg["value"])
        self.coordinator.async_set_updated_data(meteo)

    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_sensor(
                self._lookin_device.id, SensorID.Meteo, None, self._async_push_update
            )
        )
        return await super().async_added_to_hass()
