"""Setup Mullvad VPN Binary Sensors."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

BINARY_SENSORS = (
    {
        CONF_ID: "mullvad_exit_ip",
        CONF_NAME: "Mullvad Exit IP",
        CONF_DEVICE_CLASS: BinarySensorDeviceClass.CONNECTIVITY,
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN]

    async_add_entities(
        MullvadBinarySensor(coordinator, sensor) for sensor in BINARY_SENSORS
    )


class MullvadBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Represents a Mullvad binary sensor."""

    def __init__(self, coordinator, sensor):
        """Initialize the Mullvad binary sensor."""
        super().__init__(coordinator)
        self._attr_device_class = sensor[CONF_DEVICE_CLASS]
        self._attr_is_on = self.coordinator.data[sensor[CONF_ID]]
        self._attr_name = sensor[CONF_NAME]
        self._attr_unique_id = DOMAIN
