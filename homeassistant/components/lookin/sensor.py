"""The lookin integration sensor platform."""
from __future__ import annotations

import logging

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
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .aiolookin import MeteoSensor
from .const import DOMAIN
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


class LookinSensorEntity(CoordinatorEntity, SensorEntity, Entity):
    """A lookin device sensor entity."""

    _attr_should_poll = False

    def __init__(
        self, description: SensorEntityDescription, lookin_data: LookinData
    ) -> None:
        """Init the lookin sensor entity."""
        super().__init__(lookin_data.meteo_coordinator)
        self.entity_description = description
        self._lookin_device = lookin_data.lookin_device
        self._lookin_udp_subs = lookin_data.lookin_udp_subs
        self._attr_name = f"{self._lookin_device.name} {description.name}"
        self._attr_native_value = getattr(self.coordinator.data, description.key)
        self._attr_unique_id = f"{self._lookin_device.id}-{description.key}"

    def _handle_coordinator_update(self):
        """Update the state of the entity."""
        self._attr_native_value = getattr(
            self.coordinator.data, self.entity_description.key
        )
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for the onboard sensor."""
        return {
            "identifiers": {(DOMAIN, self._lookin_device.id)},
            "name": self._lookin_device.name,
            "manufacturer": "LOOK.in",
            "model": "LOOK.in 2",
            "sw_version": self._lookin_device.firmware,
        }

    @callback
    def _async_push_update(self, msg):
        """Process an update pushed via UDP."""
        LOGGER.debug("Saw push message: %s", msg)
        if msg["sensor_id"] != "FE" or msg["event_id"] not in ("00", "0"):
            return
        meteo: MeteoSensor = self.coordinator.data
        meteo.update_from_value(msg["value"])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        self.async_on_remove(
            self._lookin_udp_subs.subscribe(
                self._lookin_device.id, self._async_push_update
            )
        )
        return await super().async_added_to_hass()
