"""Support for KNX/IP sensors."""
import voluptuous as vol
from xknx.devices import Sensor as XknxSensor

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import ATTR_DISCOVER_DEVICES, DATA_KNX

CONF_STATE_ADDRESS = "state_address"
CONF_SYNC_STATE = "sync_state"
DEFAULT_NAME = "KNX Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SYNC_STATE, default=True): cv.boolean,
        vol.Required(CONF_STATE_ADDRESS): cv.string,
        vol.Required(CONF_TYPE): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up sensor(s) for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)
    else:
        async_add_entities_config(hass, config, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up sensors for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXSensor(device))
    async_add_entities(entities)


@callback
def async_add_entities_config(hass, config, async_add_entities):
    """Set up sensor for KNX platform configured within platform."""
    sensor = XknxSensor(
        hass.data[DATA_KNX].xknx,
        name=config[CONF_NAME],
        group_address_state=config[CONF_STATE_ADDRESS],
        sync_state=config[CONF_SYNC_STATE],
        value_type=config[CONF_TYPE],
    )
    hass.data[DATA_KNX].xknx.devices.add(sensor)
    async_add_entities([KNXSensor(sensor)])


class KNXSensor(Entity):
    """Representation of a KNX sensor."""

    def __init__(self, device):
        """Initialize of a KNX sensor."""
        self.device = device

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            self.async_write_ha_state()

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
    def state(self):
        """Return the state of the sensor."""
        return self.device.resolve_state()

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self.device.unit_of_measurement()

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self.device.ha_device_class()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return None
