"""Support for OpenTherm Gateway binary sensors."""
import logging

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id

from .const import BINARY_SENSOR_INFO, DATA_GATEWAYS, DATA_OPENTHERM_GW


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the OpenTherm Gateway binary sensors."""
    if discovery_info is None:
        return
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][discovery_info]
    sensors = []
    for var, info in BINARY_SENSOR_INFO.items():
        device_class = info[0]
        friendly_name_format = info[1]
        sensors.append(
            OpenThermBinarySensor(gw_dev, var, device_class, friendly_name_format)
        )
    async_add_entities(sensors)


class OpenThermBinarySensor(BinarySensorDevice):
    """Represent an OpenTherm Gateway binary sensor."""

    def __init__(self, gw_dev, var, device_class, friendly_name_format):
        """Initialize the binary sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, "{}_{}".format(var, gw_dev.gw_id), hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._state = None
        self._device_class = device_class
        self._friendly_name = friendly_name_format.format(gw_dev.name)

    async def async_added_to_hass(self):
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway binary sensor %s", self._friendly_name)
        async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    @callback
    def receive_report(self, status):
        """Handle status updates from the component."""
        self._state = bool(status.get(self._var))
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the friendly name."""
        return self._friendly_name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._device_class

    @property
    def should_poll(self):
        """Return False because entity pushes its state."""
        return False
