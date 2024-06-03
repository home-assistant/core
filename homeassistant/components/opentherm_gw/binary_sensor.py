"""Support for OpenTherm Gateway binary sensors."""

import logging

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import (
    BINARY_SENSOR_INFO,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    TRANSLATE_SOURCE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway binary sensors."""
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    async_add_entities(
        OpenThermBinarySensor(
            gw_dev,
            var,
            source,
            info[0],
            info[1],
        )
        for var, info in BINARY_SENSOR_INFO.items()
        for source in info[2]
    )


class OpenThermBinarySensor(BinarySensorEntity):
    """Represent an OpenTherm Gateway binary sensor."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False

    def __init__(self, gw_dev, var, source, device_class, friendly_name_format):
        """Initialize the binary sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{source}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._source = source
        self._attr_device_class = device_class
        if TRANSLATE_SOURCE[source] is not None:
            friendly_name_format = (
                f"{friendly_name_format} ({TRANSLATE_SOURCE[source]})"
            )
        self._attr_name = friendly_name_format.format(gw_dev.name)
        self._unsub_updates = None
        self._attr_unique_id = f"{gw_dev.gw_id}-{source}-{var}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gw_dev.gw_id)},
            manufacturer="Schelte Bron",
            model="OpenTherm Gateway",
            name=gw_dev.name,
            sw_version=gw_dev.gw_version,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway binary sensor %s", self._attr_name)
        self._unsub_updates = async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from updates from the component."""
        _LOGGER.debug("Removing OpenTherm Gateway binary sensor %s", self._attr_name)
        self._unsub_updates()

    @property
    def available(self):
        """Return availability of the sensor."""
        return self._attr_is_on is not None

    @callback
    def receive_report(self, status):
        """Handle status updates from the component."""
        state = status[self._source].get(self._var)
        self._attr_is_on = None if state is None else bool(state)
        self.async_write_ha_state()
