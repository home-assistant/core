"""Support for INSTEON dimmers via PowerLinc Modem."""

from pyinsteon.groups import (
    CO_SENSOR,
    DOOR_SENSOR,
    HEARTBEAT,
    LEAK_SENSOR_WET,
    LIGHT_SENSOR,
    LOW_BATTERY,
    MOTION_SENSOR,
    OPEN_CLOSE_SENSOR,
    SENSOR_MALFUNCTION,
    SMOKE_SENSOR,
    TEST_SENSOR,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SIGNAL_ADD_ENTITIES
from .entity import InsteonEntity
from .utils import async_add_insteon_devices, async_add_insteon_entities

SENSOR_TYPES = {
    OPEN_CLOSE_SENSOR: BinarySensorDeviceClass.OPENING,
    MOTION_SENSOR: BinarySensorDeviceClass.MOTION,
    DOOR_SENSOR: BinarySensorDeviceClass.DOOR,
    LEAK_SENSOR_WET: BinarySensorDeviceClass.MOISTURE,
    LIGHT_SENSOR: BinarySensorDeviceClass.LIGHT,
    LOW_BATTERY: BinarySensorDeviceClass.BATTERY,
    CO_SENSOR: BinarySensorDeviceClass.GAS,
    SMOKE_SENSOR: BinarySensorDeviceClass.SMOKE,
    TEST_SENSOR: BinarySensorDeviceClass.SAFETY,
    SENSOR_MALFUNCTION: BinarySensorDeviceClass.PROBLEM,
    HEARTBEAT: BinarySensorDeviceClass.PROBLEM,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Insteon binary sensors from a config entry."""

    @callback
    def async_add_insteon_binary_sensor_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            Platform.BINARY_SENSOR,
            InsteonBinarySensorEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.BINARY_SENSOR}"
    async_dispatcher_connect(hass, signal, async_add_insteon_binary_sensor_entities)
    async_add_insteon_devices(
        hass,
        Platform.BINARY_SENSOR,
        InsteonBinarySensorEntity,
        async_add_entities,
    )


class InsteonBinarySensorEntity(InsteonEntity, BinarySensorEntity):
    """A Class for an Insteon binary sensor entity."""

    def __init__(self, device, group):
        """Initialize the INSTEON binary sensor."""
        super().__init__(device, group)
        self._attr_device_class = SENSOR_TYPES.get(self._insteon_device_group.name)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return bool(self._insteon_device_group.value)
