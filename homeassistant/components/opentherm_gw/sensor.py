"""Support for OpenTherm Gateway sensors."""
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.const import CONF_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, async_generate_entity_id

from . import DOMAIN
from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW, SENSOR_INFO

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the OpenTherm Gateway sensors."""
    sensors = []
    for var, info in SENSOR_INFO.items():
        device_class = info[0]
        unit = info[1]
        friendly_name_format = info[2]
        sensors.append(
            OpenThermSensor(
                hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]],
                var,
                device_class,
                unit,
                friendly_name_format,
            )
        )

    async_add_entities(sensors)


class OpenThermSensor(Entity):
    """Representation of an OpenTherm Gateway sensor."""

    def __init__(self, gw_dev, var, device_class, unit, friendly_name_format):
        """Initialize the OpenTherm Gateway sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._value = None
        self._device_class = device_class
        self._unit = unit
        self._friendly_name = friendly_name_format.format(gw_dev.name)
        self._unsub_updates = None

    async def async_added_to_hass(self):
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway sensor %s", self._friendly_name)
        self._unsub_updates = async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from updates from the component."""
        _LOGGER.debug("Removing OpenTherm Gateway sensor %s", self._friendly_name)
        self._unsub_updates()

    @property
    def available(self):
        """Return availability of the sensor."""
        return self._value is not None

    @property
    def entity_registry_enabled_default(self):
        """Disable sensors by default."""
        return False

    @callback
    def receive_report(self, status):
        """Handle status updates from the component."""
        value = status.get(self._var)
        if isinstance(value, float):
            value = f"{value:2.1f}"
        self._value = value
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the friendly name of the sensor."""
        return self._friendly_name

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._gateway.gw_id)},
            "name": self._gateway.name,
            "manufacturer": "Schelte Bron",
            "model": "OpenTherm Gateway",
            "sw_version": self._gateway.gw_version,
        }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._gateway.gw_id}-{self._var}"

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
