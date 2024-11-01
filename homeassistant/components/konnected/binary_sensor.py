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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
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
        self._attr_is_on = data.get(ATTR_STATE)
        self._attr_device_class = data.get(CONF_TYPE)
        self._attr_unique_id = f"{device_id}-{zone_num}"
        self._attr_name = data.get(CONF_NAME)
        self._attr_device_info = DeviceInfo(
            identifiers={(KONNECTED_DOMAIN, device_id)},
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
        self._attr_is_on = state
        self.async_write_ha_state()
