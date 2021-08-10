"""Support for OpenTherm Gateway binary sensors."""
import logging
from pprint import pformat

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity
from homeassistant.const import CONF_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_registry import async_get_registry

from . import DOMAIN
from .const import (
    BINARY_SENSOR_INFO,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DEPRECATED_BINARY_SENSOR_SOURCE_LOOKUP,
    TRANSLATE_SOURCE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the OpenTherm Gateway binary sensors."""
    sensors = []
    deprecated_sensors = []
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]
    ent_reg = await async_get_registry(hass)
    for var, info in BINARY_SENSOR_INFO.items():
        device_class = info[0]
        friendly_name_format = info[1]
        status_sources = info[2]

        for source in status_sources:
            sensors.append(
                OpenThermBinarySensor(
                    gw_dev,
                    var,
                    source,
                    device_class,
                    friendly_name_format,
                )
            )

        old_style_entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        old_ent = ent_reg.async_get(old_style_entity_id)
        if old_ent and old_ent.config_entry_id == config_entry.entry_id:
            if old_ent.disabled:
                ent_reg.async_remove(old_style_entity_id)
            else:
                deprecated_sensors.append(
                    DeprecatedOpenThermBinarySensor(
                        gw_dev,
                        var,
                        device_class,
                        friendly_name_format,
                    )
                )

    sensors.extend(deprecated_sensors)

    if deprecated_sensors:
        _LOGGER.warning(
            "The following binary_sensor entities are deprecated and may "
            "no longer behave as expected. They will be removed in a "
            "future version. You can force removal of these entities by "
            "disabling them and restarting Home Assistant.\n%s",
            pformat([s.entity_id for s in deprecated_sensors]),
        )

    async_add_entities(sensors)


class OpenThermBinarySensor(BinarySensorEntity):
    """Represent an OpenTherm Gateway binary sensor."""

    def __init__(self, gw_dev, var, source, device_class, friendly_name_format):
        """Initialize the binary sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{source}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._source = source
        self._state = None
        self._device_class = device_class
        if TRANSLATE_SOURCE[source] is not None:
            friendly_name_format = (
                f"{friendly_name_format} ({TRANSLATE_SOURCE[source]})"
            )
        self._friendly_name = friendly_name_format.format(gw_dev.name)
        self._unsub_updates = None

    async def async_added_to_hass(self):
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway binary sensor %s", self._friendly_name)
        self._unsub_updates = async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from updates from the component."""
        _LOGGER.debug(
            "Removing OpenTherm Gateway binary sensor %s", self._friendly_name
        )
        self._unsub_updates()

    @property
    def available(self):
        """Return availability of the sensor."""
        return self._state is not None

    @property
    def entity_registry_enabled_default(self):
        """Disable binary_sensors by default."""
        return False

    @callback
    def receive_report(self, status):
        """Handle status updates from the component."""
        state = status[self._source].get(self._var)
        self._state = None if state is None else bool(state)
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the friendly name."""
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
        return f"{self._gateway.gw_id}-{self._source}-{self._var}"

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


class DeprecatedOpenThermBinarySensor(OpenThermBinarySensor):
    """Represent a deprecated OpenTherm Gateway Binary Sensor."""

    # pylint: disable=super-init-not-called
    def __init__(self, gw_dev, var, device_class, friendly_name_format):
        """Initialize the binary sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._source = DEPRECATED_BINARY_SENSOR_SOURCE_LOOKUP[var]
        self._state = None
        self._device_class = device_class
        self._friendly_name = friendly_name_format.format(gw_dev.name)
        self._unsub_updates = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._gateway.gw_id}-{self._var}"
