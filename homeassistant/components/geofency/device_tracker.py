"""Support for the Geofency device tracker platform."""

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN as GF_DOMAIN, TRACKER_UPDATE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Geofency config entry."""

    @callback
    def _receive_data(device, gps, location_name, attributes):
        """Fire HA event to set location."""
        if device in hass.data[GF_DOMAIN]["devices"]:
            return

        hass.data[GF_DOMAIN]["devices"].add(device)

        async_add_entities([GeofencyEntity(device, gps, location_name, attributes)])

    hass.data[GF_DOMAIN]["unsub_device_tracker"][config_entry.entry_id] = (
        async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data)
    )

    # Restore previously loaded devices
    dev_reg = dr.async_get(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.get_devices_for_config_entry_id(
            config_entry.entry_id
        )
        for identifier in device.identifiers
    }

    if dev_ids:
        hass.data[GF_DOMAIN]["devices"].update(dev_ids)
        async_add_entities(GeofencyEntity(dev_id) for dev_id in dev_ids)


class GeofencyEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device, gps=None, location_name=None, attributes=None):
        """Set up Geofency entity."""
        self._attr_extra_state_attributes = attributes or {}
        self._name = device
        self._attr_location_name = location_name
        if gps:
            self._attr_latitude = gps[0]
            self._attr_longitude = gps[1]
        self._unsub_dispatcher = None
        self._attr_unique_id = device
        self._attr_device_info = DeviceInfo(
            identifiers={(GF_DOMAIN, device)},
            name=device,
        )

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        await super().async_added_to_hass()
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

        if self._attr_extra_state_attributes:
            return

        if (state := await self.async_get_last_state()) is None:
            self._attr_latitude = None
            self._attr_longitude = None
            return

        attr = state.attributes
        self._attr_latitude = attr.get(ATTR_LATITUDE)
        self._attr_longitude = attr.get(ATTR_LONGITUDE)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up after entity before removal."""
        await super().async_will_remove_from_hass()
        self._unsub_dispatcher()
        self.hass.data[GF_DOMAIN]["devices"].remove(self.unique_id)

    @callback
    def _async_receive_data(self, device, gps, location_name, attributes):
        """Mark the device as seen."""
        if device != self._name:
            return

        self._attr_extra_state_attributes.update(attributes)
        self._attr_location_name = location_name
        self._attr_latitude = gps[0]
        self._attr_longitude = gps[1]
        self.async_write_ha_state()
