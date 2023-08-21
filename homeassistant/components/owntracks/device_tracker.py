"""Device tracker platform that adds support for OwnTracks over MQTT."""
from homeassistant.components.device_tracker import (
    ATTR_SOURCE_TYPE,
    DOMAIN,
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN as OT_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OwnTracks based off an entry."""
    # Restore previously loaded devices
    dev_reg = dr.async_get(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.values()
        for identifier in device.identifiers
        if identifier[0] == OT_DOMAIN
    }

    entities = []
    for dev_id in dev_ids:
        entity = hass.data[OT_DOMAIN]["devices"][dev_id] = OwnTracksEntity(dev_id)
        entities.append(entity)

    @callback
    def _receive_data(dev_id, **data):
        """Receive set location."""
        entity = hass.data[OT_DOMAIN]["devices"].get(dev_id)

        if entity is not None:
            entity.update_data(data)
            return

        entity = hass.data[OT_DOMAIN]["devices"][dev_id] = OwnTracksEntity(dev_id, data)
        async_add_entities([entity])

    hass.data[OT_DOMAIN]["context"].set_async_see(_receive_data)

    async_add_entities(entities)


class OwnTracksEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, dev_id, data=None):
        """Set up OwnTracks entity."""
        self._dev_id = dev_id
        self._data = data or {}
        self.entity_id = f"{DOMAIN}.{dev_id}"

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._dev_id

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._data.get("battery")

    @property
    def extra_state_attributes(self):
        """Return device specific attributes."""
        return self._data.get("attributes")

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._data.get("gps_accuracy")

    @property
    def latitude(self):
        """Return latitude value of the device."""
        # Check with "get" instead of "in" because value can be None
        if self._data.get("gps"):
            return self._data["gps"][0]

        return None

    @property
    def longitude(self):
        """Return longitude value of the device."""
        # Check with "get" instead of "in" because value can be None
        if self._data.get("gps"):
            return self._data["gps"][1]

        return None

    @property
    def location_name(self):
        """Return a location name for the current location of the device."""
        return self._data.get("location_name")

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return self._data.get("source_type", SourceType.GPS)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        device_info = DeviceInfo(identifiers={(OT_DOMAIN, self._dev_id)})
        if "host_name" in self._data:
            device_info["name"] = self._data["host_name"]
        return device_info

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()

        # Don't restore if we got set up with data.
        if self._data:
            return

        if (state := await self.async_get_last_state()) is None:
            return

        attr = state.attributes
        self._data = {
            "host_name": state.name,
            "gps": (attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE)),
            "gps_accuracy": attr.get(ATTR_GPS_ACCURACY),
            "battery": attr.get(ATTR_BATTERY_LEVEL),
            "source_type": attr.get(ATTR_SOURCE_TYPE),
        }

    @callback
    def update_data(self, data):
        """Mark the device as seen."""
        self._data = data
        if self.hass:
            self.async_write_ha_state()
