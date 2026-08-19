"""Support for exposing Concord232 zones as binary sensors."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .alarm_control_panel import _async_import_yaml
from .const import DOMAIN
from .coordinator import Concord232ConfigEntry, Concord232Coordinator

PARALLEL_UPDATES = 0

CONF_EXCLUDE_ZONES = "exclude_zones"
CONF_ZONE_TYPES = "zone_types"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5007

ZONE_TYPES_SCHEMA = vol.Schema({cv.positive_int: BINARY_SENSOR_DEVICE_CLASSES_SCHEMA})

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_EXCLUDE_ZONES, default=[]): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_ZONE_TYPES, default={}): ZONE_TYPES_SCHEMA,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML platform configuration and create a config entry."""
    await _async_import_yaml(hass, config)


def get_opening_type(zone: dict[str, Any]) -> BinarySensorDeviceClass:
    """Return the device class guessed from the zone name."""
    if "MOTION" in zone["name"]:
        return BinarySensorDeviceClass.MOTION
    if "KEY" in zone["name"]:
        return BinarySensorDeviceClass.SAFETY
    if "SMOKE" in zone["name"]:
        return BinarySensorDeviceClass.SMOKE
    if "WATER" in zone["name"]:
        return BinarySensorDeviceClass.MOISTURE
    return BinarySensorDeviceClass.OPENING


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Concord232ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Concord232 zone binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        Concord232ZoneSensor(entry, zone) for zone in coordinator.data.zones
    )


class Concord232ZoneSensor(
    CoordinatorEntity[Concord232Coordinator], BinarySensorEntity
):
    """Representation of a Concord232 zone as a binary sensor."""

    _attr_has_entity_name = True

    def __init__(self, entry: Concord232ConfigEntry, zone: dict[str, Any]) -> None:
        """Initialize the Concord232 zone binary sensor."""
        super().__init__(entry.runtime_data)
        self._number: int = zone["number"]
        self._attr_unique_id = f"{entry.entry_id}_zone_{self._number}"
        self._attr_name = zone["name"]
        self._attr_device_class = get_opening_type(zone)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )

    def _zone(self) -> dict[str, Any] | None:
        """Return this zone's current data."""
        return next(
            (
                zone
                for zone in self.coordinator.data.zones
                if zone["number"] == self._number
            ),
            None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True when the coordinator and the zone are available."""
        return super().available and self._zone() is not None

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the zone is faulted (open, tripped or abnormal)."""
        zone = self._zone()
        if zone is None:
            return False
        # The original concord232 server reports zone state as a string; the
        # actively maintained fork reports a list of states. Accept both.
        state = zone["state"]
        states = state if isinstance(state, list) else [state]
        return states != ["Normal"]
