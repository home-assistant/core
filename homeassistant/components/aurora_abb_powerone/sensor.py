"""Support for Aurora ABB PowerOne Solar Photvoltaic (PV) inverter."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aurorapy.client import AuroraError, AuroraSerialClient
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_NAME,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

from .aurora_device import AuroraEntity
from .const import DEFAULT_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = [
    SensorEntityDescription(
        key="instantaneouspower",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Power Output",
    ),
    SensorEntityDescription(
        key="temp",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Temperature",
    ),
    SensorEntityDescription(
        key="totalenergy",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        name="Total Energy",
    ),
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_ADDRESS, default=DEFAULT_ADDRESS): cv.positive_int,
        vol.Optional(CONF_NAME, default="Solar PV"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up based on configuration.yaml (DEPRECATED)."""
    _LOGGER.warning(
        "Loading aurora_abb_powerone via platform config is deprecated; The configuration"
        " has been migrated to a config entry and can be safely removed from configuration.yaml"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
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

        except AuroraError as error:
            self._attr_state = None
            self._attr_native_value = None
            self._attr_available = False
            # aurorapy does not have different exceptions (yet) for dealing
            # with timeout vs other comms errors.
            # This means the (normal) situation of no response during darkness
            # raises an exception.
            # aurorapy (gitlab) pull request merged 29/5/2019. When >0.2.6 is
            # released, this could be modified to :
            # except AuroraTimeoutError as e:
            # Workaround: look at the text of the exception
            if "No response after" in str(error):
                _LOGGER.debug("No response from inverter (could be dark)")
            else:
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
