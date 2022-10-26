"""Platform for sensor integration."""
from __future__ import annotations
import logging
import voluptuous as vol
from datetime import timedelta
from .sipphone import sip_device


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv


from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME,
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_PATH,
    CONF_URL,
)

_LOGGER = logging.getLogger(__name__)
# Time between updating data from GitHub
SCAN_INTERVAL = timedelta(seconds=1)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required('server'): cv.string,
        vol.Required('port'): cv.positive_int,
        vol.Required('username'): cv.string,
        vol.Required('password'): cv.string,
        vol.Required('bind_ip'): cv.string,
        vol.Required('name'): cv.string,
        vol.Required('message'): cv.string,
        vol.Required('notify'): cv.string,
    }
)


def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    print("conf username:"+config['username'])
    """Set up the sensor platform."""
    # async_add_entities([IntercomSensor(sip_device(server="192.168.2.9",port=5060,
    #     username= "User5", password="1234",bind_ip="192.168.2.147"))])
    # config["bind_ip"] = "127.0.0.1"
    async_add_entities([IntercomSensor(
        sip_device(server=config['server'],port=config['port'],
        username= config["username"], password=config["password"],bind_ip=config["bind_ip"])
        ,config,
        hass)])


class IntercomSensor(SensorEntity):
    """Representation of a Sensor."""

    #_attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = SensorDeviceClass.INTERCOM
    #_attr_state_class = SensorStateClass.TOTAL
    _attr_available: bool
    def __init__(self,phone,config,hass) -> None:
        super().__init__()
        self._phone=phone
        self._config = config
        self._hass =hass
        self._once = True

    @property
    def should_poll(self) -> bool:
        """No polling needed for a sensor."""
        return True
    
    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._config['name']
    

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = self._phone._state
        if (self._phone._state == "idle"):
            self._once = True
        if (self._phone._state == "ringing" and self._once):
            self._once = False

            mobs = self._config['notify'].split(',')
            for mob in mobs:
                self.hass.services.call(
                    'notify',
                    mob,
                    {"message": self._config['message'],
                    "data": {
                        "actions": [
                            {
                                "action": "ANSWER",
                                "title": "Answer Intercom",
                                "icon": "sfsymbols:bell"
                            },
                            {
                                "action": "DECLINE",
                                "title": "Decline Intercom",
                                "icon": "sfsymbols:bell.slash"
                            }
                        ]
                        }
                    },
                )