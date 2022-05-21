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
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Insteon binary sensors from a config entry."""

    @callback
    def async_add_insteon_binary_sensor_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            BINARY_SENSOR_DOMAIN,
            InsteonBinarySensorEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{BINARY_SENSOR_DOMAIN}"
    async_dispatcher_connect(hass, signal, async_add_insteon_binary_sensor_entities)
    async_add_insteon_binary_sensor_entities()


class InsteonBinarySensorEntity(InsteonEntity, BinarySensorEntity):
    """A Class for an Insteon binary sensor entity."""

    def __init__(self, device, group):
        """Initialize the INSTEON binary sensor."""
        super().__init__(device, group)
        self._sensor_type = SENSOR_TYPES.get(self._insteon_device_group.name)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return bool(self._insteon_device_group.value)
