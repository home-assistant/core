"""Support for OpenTherm Gateway sensors."""
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW, SENSOR_INFO, TRANSLATE_SOURCE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway sensors."""
    sensors = []
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]
    for var, info in SENSOR_INFO.items():
        device_class = info[0]
        unit = info[1]
        friendly_name_format = info[2]
        status_sources = info[3]

        for source in status_sources:
            sensors.append(
                OpenThermSensor(
                    gw_dev,
                    var,
                    source,
                    device_class,
                    unit,
                    friendly_name_format,
                )
            )

    async_add_entities(sensors)


class OpenThermSensor(SensorEntity):
    """Representation of an OpenTherm Gateway sensor."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False

    def __init__(self, gw_dev, var, source, device_class, unit, friendly_name_format):
        """Initialize the OpenTherm Gateway sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{source}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._source = source
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
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
        _LOGGER.debug("Added OpenTherm Gateway sensor %s", self._attr_name)
        self._unsub_updates = async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from updates from the component."""
        _LOGGER.debug("Removing OpenTherm Gateway sensor %s", self._attr_name)
        self._unsub_updates()

    @property
    def available(self):
        """Return availability of the sensor."""
        return self._attr_native_value is not None

    @callback
    def receive_report(self, status):
        """Handle status updates from the component."""
        value = status[self._source].get(self._var)
        if isinstance(value, float):
            value = f"{value:2.1f}"
        self._attr_native_value = value
        self.async_write_ha_state()
