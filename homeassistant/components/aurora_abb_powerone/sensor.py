"""Support for Aurora ABB PowerOne Solar Photovoltaic (PV) inverter."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aurorapy.client import AuroraError, AuroraSerialClient, AuroraTimeoutError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aurora_device import AuroraEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = [
    SensorEntityDescription(
        key="instantaneouspower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        name="Power Output",
    ),
    SensorEntityDescription(
        key="temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        name="Temperature",
    ),
    SensorEntityDescription(
        key="totalenergy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Total Energy",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up aurora_abb_powerone sensor based on a config entry."""
    entities = []

    client = hass.data[DOMAIN][config_entry.entry_id]
    data = config_entry.data

    for sens in SENSOR_TYPES:
        entities.append(AuroraSensor(client, data, sens))

    _LOGGER.debug("async_setup_entry adding %d entities", len(entities))
    async_add_entities(entities, True)


class AuroraSensor(AuroraEntity, SensorEntity):
    """Representation of a Sensor on a Aurora ABB PowerOne Solar inverter."""

    def __init__(
        self,
        client: AuroraSerialClient,
        data: Mapping[str, Any],
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(client, data)
        self.entity_description = entity_description
        self.available_prev = True

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            self.available_prev = self._attr_available
            self.client.connect()
            if self.entity_description.key == "instantaneouspower":
                # read ADC channel 3 (grid power output)
                power_watts = self.client.measure(3, True)
                self._attr_native_value = round(power_watts, 1)
            elif self.entity_description.key == "temp":
                temperature_c = self.client.measure(21)
                self._attr_native_value = round(temperature_c, 1)
            elif self.entity_description.key == "totalenergy":
                energy_wh = self.client.cumulated_energy(5)
                self._attr_native_value = round(energy_wh / 1000, 2)
            self._attr_available = True

        except AuroraTimeoutError:
            self._attr_state = None
            self._attr_native_value = None
            self._attr_available = False
            _LOGGER.debug("No response from inverter (could be dark)")
        except AuroraError as error:
            self._attr_state = None
            self._attr_native_value = None
            self._attr_available = False
            raise error
        finally:
            if self._attr_available != self.available_prev:
                if self._attr_available:
                    _LOGGER.info("Communication with %s back online", self.name)
                else:
                    _LOGGER.warning(
                        "Communication with %s lost",
                        self.name,
                    )
            if self.client.serline.isOpen():
                self.client.close()
