"""
Support for KNX/IP binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.knx/
"""

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.components.knx import (
    ATTR_DISCOVER_DEVICES, DATA_KNX, KNXAutomation)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_DEVICE_CLASS = 'device_class'
CONF_SIGNIFICANT_BIT = 'significant_bit'
CONF_DEFAULT_SIGNIFICANT_BIT = 1
CONF_AUTOMATION = 'automation'
CONF_HOOK = 'hook'
CONF_DEFAULT_HOOK = 'on'
CONF_COUNTER = 'counter'
CONF_DEFAULT_COUNTER = 1
CONF_ACTION = 'action'
CONF_RESET_AFTER = 'reset_after'

CONF__ACTION = 'turn_off_action'

DEFAULT_NAME = 'KNX Binary Sensor'
DEPENDENCIES = ['knx']

AUTOMATION_SCHEMA = vol.Schema({
    vol.Optional(CONF_HOOK, default=CONF_DEFAULT_HOOK): cv.string,
    vol.Optional(CONF_COUNTER, default=CONF_DEFAULT_COUNTER): cv.port,
    vol.Required(CONF_ACTION): cv.SCRIPT_SCHEMA
})

AUTOMATIONS_SCHEMA = vol.All(
    cv.ensure_list,
    [AUTOMATION_SCHEMA]
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): cv.string,
    vol.Optional(CONF_SIGNIFICANT_BIT, default=CONF_DEFAULT_SIGNIFICANT_BIT):
        cv.positive_int,
    vol.Optional(CONF_RESET_AFTER): cv.positive_int,
    vol.Optional(CONF_AUTOMATION): AUTOMATIONS_SCHEMA,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up binary sensor(s) for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)
    else:
        async_add_entities_config(hass, config, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up binary sensors for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXBinarySensor(device))
    async_add_entities(entities)


@callback
def async_add_entities_config(hass, config, async_add_entities):
    """Set up binary senor for KNX platform configured within platform."""
    name = config.get(CONF_NAME)
    import xknx
    binary_sensor = xknx.devices.BinarySensor(
        hass.data[DATA_KNX].xknx,
        name=name,
        group_address=config.get(CONF_ADDRESS),
        device_class=config.get(CONF_DEVICE_CLASS),
        significant_bit=config.get(CONF_SIGNIFICANT_BIT),
        reset_after=config.get(CONF_RESET_AFTER))
    hass.data[DATA_KNX].xknx.devices.add(binary_sensor)

    entity = KNXBinarySensor(binary_sensor)
    automations = config.get(CONF_AUTOMATION)
    if automations is not None:
        for automation in automations:
            counter = automation.get(CONF_COUNTER)
            hook = automation.get(CONF_HOOK)
            action = automation.get(CONF_ACTION)
            entity.automations.append(KNXAutomation(
                hass=hass, device=binary_sensor, hook=hook,
                action=action, counter=counter))
    async_add_entities([entity])


class KNXBinarySensor(BinarySensorDevice):
    """Representation of a KNX binary sensor."""

    def __init__(self, device):
        """Initialize of KNX binary sensor."""
        self.device = device
        self.automations = []

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        async def after_update_callback(device):
            """Call after device was updated."""
            await self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self.device.device_class

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.device.is_on()
