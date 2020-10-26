"""Support for Honeywell (US) Total Connect Comfort climate systems sensors."""


import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_REGION,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import CLIENT_KEY_COORDINATOR, HoneywellDevice

CONF_DEV_ID = "thermostat"
CONF_LOC_ID = "location"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_REGION),
    PLATFORM_SCHEMA.extend(
        {
            # there are no options to specify.
            # we automatically populate the sensors provided
        }
    ),
)


class ThermostatSensor(HoneywellDevice, Entity):
    """Base class for honeywell thermostat sensor."""

    def __init__(self, coordinator, device, get_data_function, display_name):
        """Init the sensor, pass in reference to coordinator, somecomfort device, the type str of this sensor, and entity display name."""
        HoneywellDevice.__init__(self, coordinator, device)
        self._get_data_function = get_data_function
        self._display_name = display_name

    @property
    def name(self):
        """Return the display name of the sensor entity."""
        return self._display_name + " " + self._device.name

    @property
    def state(self):
        """Return the current state of the entity."""
        return self._device.get_data_function()


class TemperatureSensor(ThermostatSensor):
    """Honeywell temperature sensor class."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement, either C or F."""
        return TEMP_CELSIUS if self._device.temperature_unit == "C" else TEMP_FAHRENHEIT

    @property
    def icon(self):
        """Set the default icon to be a thermometer."""
        return "mdi:thermometer"

    @property
    def device_class(self):
        """Set the device class as a temperature sensor."""
        return DEVICE_CLASS_TEMPERATURE


class HumiditySensor(ThermostatSensor):
    """Honeywell humidity sensor class."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement, % for relative humidity."""
        return "%"

    @property
    def icon(self):
        """Set the default icon to be a water droplet with % label."""
        return "mdi:water-percent"

    @property
    def device_class(self):
        """Set the device class as a humidity sensor."""
        return DEVICE_CLASS_HUMIDITY


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up sensors."""
    _LOGGER.info("setting up honeywell sensors")

    coordinator = hass.data[CLIENT_KEY_COORDINATOR]
    client = coordinator.data

    if coordinator.data is None:
        await coordinator.async_refresh()
    client = coordinator.data
    if client is None:
        raise PlatformNotReady

    dev_id = config.get(CONF_DEV_ID)
    loc_id = config.get(CONF_LOC_ID)

    sensors_list = []
    for location in client.locations_by_id.values():
        for device in location.devices_by_id.values():
            if (not loc_id or location.locationid == loc_id) and (
                not dev_id or device.deviceid == dev_id
            ):
                sensors_list.append(
                    TemperatureSensor(
                        coordinator,
                        device,
                        device.current_temperature,
                        "Indoor Temperature",
                    )
                )
                sensors_list.append(
                    HumiditySensor(
                        coordinator, device, device.current_humidity, "Indoor Humidity"
                    )
                )
                if not device.outdoor_temperature() is None:
                    sensors_list.append(
                        TemperatureSensor(
                            coordinator,
                            device,
                            device.outdoor_temperature,
                            "Outdoor Temperature",
                        )
                    )
                if not device.outdoor_humidity() is None:
                    sensors_list.append(
                        HumiditySensor(
                            coordinator,
                            device,
                            device.outdoor_humidity,
                            "Outdoor Humidity",
                        )
                    )

    async_add_entities(sensors_list)
