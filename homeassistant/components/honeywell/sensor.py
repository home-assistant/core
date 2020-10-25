"""Support for Honeywell (US) Total Connect Comfort climate systems sensors."""



from . import climate
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_CELSIUS
import somecomfort
from . import client_key_coordinator
from . import HoneywellDevice


import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import PlatformNotReady


from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE
)

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
    def __init__(
        self, coordinator, device, sensor_type, display_name
    ):
        HoneywellDevice.__init__(self, coordinator, device)
        self._sensor_type = sensor_type
        self._display_name = display_name

    @property
    def name(self):
        return self._display_name + " " + self._device.name
        
    @property
    def state(self):
        return self._device._data["uiData"][self._sensor_type]


class TemperatureSensor(ThermostatSensor):
    def __init__(
        self, coordinator, device, sensor_type, display_name
    ):
        super().__init__(coordinator, device, sensor_type, display_name)
        self._sensor_type = sensor_type

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS if self._device.temperature_unit == "C" else TEMP_FAHRENHEIT
            
    @property
    def icon(self):
        return "mdi:thermometer"
        
    @property
    def device_class(self):
        return DEVICE_CLASS_TEMPERATURE

class HumiditySensor(ThermostatSensor):
    def __init__(
        self, coordinator, device, sensor_type, display_name
    ):
        super().__init__(coordinator, device, sensor_type, display_name)
        self._sensor_type = sensor_type

    @property
    def unit_of_measurement(self):
        return "%"      

    @property
    def icon(self):
        return "mdi:water-percent"         

    @property
    def device_class(self):
        return DEVICE_CLASS_HUMIDITY 

    
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Honeywell thermostat."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    _LOGGER.info("setting up honeywell sensors")
    
    coordinator = hass.data[client_key_coordinator]
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
            if ((not loc_id or location.locationid == loc_id)
            and (not dev_id or device.deviceid == dev_id) ):
                if device._data["uiData"]["DispTemperatureAvailable"]:
                    sensors_list.append(TemperatureSensor(
                                          coordinator,
                                          device,
                                          "DispTemperature",
                                          "Indoor Temperature"
                                       ))
                if device._data["uiData"]["IndoorHumiditySensorAvailable"]:
                    sensors_list.append(HumiditySensor(
                                          coordinator,
                                          device,
                                          "IndoorHumidity",
                                          "Indoor Humidity"
                                       ))
                if device._data["uiData"]["OutdoorTemperatureAvailable"]:
                    sensors_list.append(TemperatureSensor(
                                          coordinator,
                                          device,
                                          "OutdoorTemperature",
                                          "Outdoor Temperature"
                                       ))
                if device._data["uiData"]["OutdoorHumidityAvailable"]:
                    sensors_list.append(HumiditySensor(
                                          coordinator,
                                          device,
                                          "OutdoorHumidity",
                                          "Outdoor Humidity"
                                       ))
        
    async_add_entities(sensors_list)