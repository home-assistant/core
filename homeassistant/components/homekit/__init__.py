import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME, CONF_IP_ADDRESS, CONF_PORT, CONF_ENTITIES, CONF_TYPE,
    ATTR_FRIENDLY_NAME, 
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

from homeassistant.components.homekit.const import (
    NAME_TEMPERATURE, TYPE_SENSOR_TEMPERATURE, NAME_COVER, TYPE_COVER)
from homeassistant.components.homekit.cover import Window
from homeassistant.components.homekit.sensor import TemperatureSensor

from pyhap.accessory import Bridge
from pyhap.accessory_driver import AccessoryDriver


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'homekit'
REQUIREMENTS = ['HAP-python==1.1.2']

CONF_PIN_CODE = 'pincode'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All({
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT): vol.Coerce(int),
        vol.Optional(CONF_PIN_CODE): cv.string,
        vol.Optional(CONF_ENTITIES): vol.Schema({
            vol.Required(cv.entity_id): vol.All({
                vol.Required(CONF_TYPE): cv.string,
                vol.Optional(CONF_NAME): cv.string,
            }),
        }),
    })
}, extra=vol.ALLOW_EXTRA)

@asyncio.coroutine
def async_setup(hass, config):
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    conf = config[DOMAIN]
    name = conf.get(CONF_NAME, 'homeassistant')
    ip = conf.get(CONF_IP_ADDRESS, '127.0.0.1')
    port = conf.get(CONF_PORT, 51826)
    pin = conf.get(CONF_PIN_CODE, '123-45-678')
    entities = conf.get(CONF_ENTITIES)

    homekit_bridge = []
    homekit_bridge.append(HomekitBridge(hass, name, ip, port, pin, entities))

    yield from component.async_add_entities(homekit_bridge)
    return True


class HomekitBridge(Entity):

    def __init__(self, hass, name, ip, port, pin, entities):
        self._hass = hass
        self._name = name
        self._ip = ip
        self._port = port
        self._pin = str.encode(pin)
        self._entities = entities
        self.path = self._hass.config.path('accessory.state')
        self.bridge = Bridge(self._name, pincode=self._pin)
        self.driver = None

    def setup_accessories(self):
        for entity_id, desc in self._entities.items():
            if desc[CONF_TYPE] == TYPE_SENSOR_TEMPERATURE:
                name = desc.get(CONF_NAME, NAME_TEMPERATURE)
                acc = TemperatureSensor(self._hass, _LOGGER, entity_id,
                                        display_name=name)
            elif desc[CONF_TYPE] == TYPE_COVER:
                name = desc.get(CONF_NAME, NAME_COVER)
                acc = Window(self._hass, _LOGGER, entity_id, display_name=name)
            else:
                continue
            self.bridge.add_accessory(acc)


    @asyncio.coroutine
    def async_added_to_hass(self):

        @callback
        def start_driver(event):
            self.setup_accessories()
            _LOGGER.debug('Driver start')
            self.driver = AccessoryDriver(self.bridge, self._port,
                                          self._ip, self.path)
            self.driver.start()

        @callback
        def homeassistant_stop(event):
            _LOGGER.debug('Driver stop')
            self.driver.stop()

        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, start_driver)
        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, homeassistant_stop)
