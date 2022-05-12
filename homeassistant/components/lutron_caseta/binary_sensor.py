"""Support for Lutron Caseta Occupancy/Vacancy Sensors."""
from pylutron_caseta import OCCUPANCY_GROUP_OCCUPIED

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SUGGESTED_AREA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as CASETA_DOMAIN, LutronCasetaDevice, _area_and_name_from_name
from .const import BRIDGE_DEVICE, BRIDGE_LEAP, CONFIG_URL, MANUFACTURER, UNASSIGNED_AREA


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta binary_sensor platform.

    Adds occupancy groups from the Caseta bridge associated with the
    config_entry as binary_sensor entities.
    """
    entities = []
    data = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data[BRIDGE_LEAP]
    bridge_device = data[BRIDGE_DEVICE]
    occupancy_groups = bridge.occupancy_groups

    for occupancy_group in occupancy_groups.values():
        entity = LutronOccupancySensor(occupancy_group, bridge, bridge_device)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronOccupancySensor(LutronCasetaDevice, BinarySensorEntity):
    """Representation of a Lutron occupancy group."""

    def __init__(self, device, bridge, bridge_device):
        """Init an occupancy sensor."""
        super().__init__(device, bridge, bridge_device)
        info = DeviceInfo(
            identifiers={(CASETA_DOMAIN, self.unique_id)},
            manufacturer=MANUFACTURER,
            model="Lutron Occupancy",
            name=self.name,
            via_device=(CASETA_DOMAIN, self._bridge_device["serial"]),
            configuration_url=CONFIG_URL,
            entry_type=DeviceEntryType.SERVICE,
        )
        area, _ = _area_and_name_from_name(device["name"])
        if area != UNASSIGNED_AREA:
            info[ATTR_SUGGESTED_AREA] = area
        self._attr_device_info = info

    @property
    def device_class(self):
        """Flag supported features."""
        return BinarySensorDeviceClass.OCCUPANCY

    @property
    def is_on(self):
        """Return the brightness of the light."""
        return self._device["status"] == OCCUPANCY_GROUP_OCCUPIED

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_write_ha_state
        )

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"occupancygroup_{self.device_id}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id}
