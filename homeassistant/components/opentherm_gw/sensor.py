"""Support for OpenTherm Gateway sensors."""
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, async_generate_entity_id

from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW, SENSOR_INFO


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the OpenTherm Gateway sensors."""
    if discovery_info is None:
        return
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][discovery_info]
    sensors = []
    for var, info in SENSOR_INFO.items():
        device_class = info[0]
        unit = info[1]
        friendly_name_format = info[2]
        sensors.append(
            OpenThermSensor(gw_dev, var, device_class, unit, friendly_name_format)
        )
    async_add_entities(sensors)


class OpenThermSensor(Entity):
    """Representation of an OpenTherm Gateway sensor."""

    def __init__(self, gw_dev, var, device_class, unit, friendly_name_format):
        """Initialize the OpenTherm Gateway sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, "{}_{}".format(var, gw_dev.gw_id), hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._value = None
        self._device_class = device_class
        self._unit = unit
        self._friendly_name = friendly_name_format.format(gw_dev.name)

    async def async_added_to_hass(self):
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway sensor %s", self._friendly_name)
        async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    @callback
    def receive_report(self, status):
        """Handle status updates from the component."""
        value = status.get(self._var)
        if isinstance(value, float):
            value = "{:2.1f}".format(value)
        self._value = value
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the friendly name of the sensor."""
        return self._friendly_name

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the device."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def should_poll(self):
        """Return False because entity pushes its state."""
        return False
