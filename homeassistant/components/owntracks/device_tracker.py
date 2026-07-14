"""Device tracker platform that adds support for OwnTracks over MQTT."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from typing import Any, override

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    DeviceTrackerEntityStateAttribute,
    SourceType,
    TrackerEntity,
    TrackerEntityStateAttribute,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, EntityStateAttribute
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ADDRESS,
    ATTR_BATTERY_STATUS,
    ATTR_COURSE,
    ATTR_TID,
    ATTR_UPDATE_TIMESTAMP,
    ATTR_VELOCITY,
    DOMAIN,
)

_RESTORED_OWNTRACKS_ATTRIBUTES: tuple[str, ...] = (
    ATTR_ADDRESS,
    ATTR_BATTERY_STATUS,
    ATTR_COURSE,
    ATTR_TID,
    ATTR_UPDATE_TIMESTAMP,
    ATTR_VELOCITY,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OwnTracks based off an entry."""
    # Restore previously loaded devices
    dev_reg = dr.async_get(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.get_devices_for_config_entry_id(entry.entry_id)
        for identifier in device.identifiers
    }

    entities = []
    for dev_id in dev_ids:
        entity = hass.data[DOMAIN]["devices"][dev_id] = OwnTracksEntity(dev_id)
        entities.append(entity)

    @callback
    def _receive_data(dev_id, **data):
        """Receive set location."""
        entity = hass.data[DOMAIN]["devices"].get(dev_id)

        if entity is not None:
            entity.update_data(data)
            return

        entity = hass.data[DOMAIN]["devices"][dev_id] = OwnTracksEntity(dev_id, data)
        async_add_entities([entity])

    hass.data[DOMAIN]["context"].set_async_see(_receive_data)

    async_add_entities(entities)


class OwnTracksEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, dev_id: str, data: dict[str, Any] | None = None) -> None:
        """Set up OwnTracks entity."""
        self._dev_id = dev_id
        self._data = data or {}
        self.entity_id = f"{DEVICE_TRACKER_DOMAIN}.{dev_id}"

    @property
    @override
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self._dev_id

    @property
    @override
    def battery_level(self) -> int | None:
        """Return the battery level of the device."""
        return self._data.get("battery")

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific attributes."""
        return self._data.get("attributes")

    @property
    @override
    def location_accuracy(self) -> float:
        """Return the gps accuracy of the device."""
        return self._data.get("gps_accuracy", 0)

    @property
    @override
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        # Check with "get" instead of "in" because value can be None
        if self._data.get("gps"):
            return self._data["gps"][0]

        return None

    @property
    @override
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        # Check with "get" instead of "in" because value can be None
        if self._data.get("gps"):
            return self._data["gps"][1]

        return None

    @property
    @override
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        return self._data.get("location_name")

    @property
    @override
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return self._data.get("source_type", SourceType.GPS)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        device_info = DeviceInfo(identifiers={(DOMAIN, self._dev_id)})
        if "host_name" in self._data:
            device_info["name"] = self._data["host_name"]
        return device_info

    @override
    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()

        # Don't restore if we got set up with data.
        if self._data:
            return

        if (state := await self.async_get_last_state()) is None:
            return

        attr = state.attributes
        attributes = {
            key: attr[key] for key in _RESTORED_OWNTRACKS_ATTRIBUTES if key in attr
        }
        if isinstance(update_timestamp := attributes.get(ATTR_UPDATE_TIMESTAMP), str):
            attributes[ATTR_UPDATE_TIMESTAMP] = dt_util.parse_datetime(update_timestamp)

        self._data = {
            "host_name": state.name,
            "gps": (
                attr.get(EntityStateAttribute.LATITUDE),
                attr.get(EntityStateAttribute.LONGITUDE),
            ),
            "gps_accuracy": attr.get(TrackerEntityStateAttribute.GPS_ACCURACY),
            "battery": attr.get(ATTR_BATTERY_LEVEL),
            "source_type": attr.get(DeviceTrackerEntityStateAttribute.SOURCE_TYPE),
            "attributes": attributes,
        }

    @callback
    def update_data(self, data):
        """Mark the device as seen."""
        self._data = data
        if self.hass:
            self.async_write_ha_state()
