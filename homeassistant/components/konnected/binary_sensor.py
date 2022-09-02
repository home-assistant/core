"""Support for wired binary sensors attached to a Konnected device."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    CONF_BINARY_SENSORS,
    CONF_DEVICES,
    CONF_NAME,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as KONNECTED_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors attached to a Konnected device from a config entry."""
    data = hass.data[KONNECTED_DOMAIN]
    device_id = config_entry.data["id"]
    sensors = [
        KonnectedBinarySensor(device_id, pin_num, pin_data)
        for pin_num, pin_data in data[CONF_DEVICES][device_id][
            CONF_BINARY_SENSORS
        ].items()
    ]
    async_add_entities(sensors)


class KonnectedBinarySensor(BinarySensorEntity):
    """Representation of a Konnected binary sensor."""

    _attr_should_poll = False

    def __init__(self, device_id, zone_num, data):
        """Initialize the Konnected binary sensor."""
        self._data = data
        self._device_id = device_id
        self._zone_num = zone_num
        self._state = self._data.get(ATTR_STATE)
        self._device_class = self._data.get(CONF_TYPE)
        self._unique_id = f"{device_id}-{zone_num}"
        self._name = self._data.get(CONF_NAME)

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(KONNECTED_DOMAIN, self._device_id)},
        )

    async def async_added_to_hass(self) -> None:
        """Store entity_id and register state change callback."""
        self._data[ATTR_ENTITY_ID] = self.entity_id
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"konnected.{self.entity_id}.update", self.async_set_state
            )
        )

    @callback
    def async_set_state(self, state):
        """Update the sensor's state."""
        self._state = state
        self.async_write_ha_state()
