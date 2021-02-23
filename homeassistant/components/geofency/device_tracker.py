"""Support for the Geofency device tracker platform."""
from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN as GF_DOMAIN, TRACKER_UPDATE


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Geofency config entry."""

    @callback
    def _receive_data(device, gps, location_name, attributes):
        """Fire HA event to set location."""
        if device in hass.data[GF_DOMAIN]["devices"]:
            return

        hass.data[GF_DOMAIN]["devices"].add(device)

        async_add_entities([GeofencyEntity(device, gps, location_name, attributes)])

    hass.data[GF_DOMAIN]["unsub_device_tracker"][
        config_entry.entry_id
    ] = async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data)

    # Restore previously loaded devices
    dev_reg = await device_registry.async_get_registry(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.values()
        for identifier in device.identifiers
        if identifier[0] == GF_DOMAIN
    }

    if dev_ids:
        hass.data[GF_DOMAIN]["devices"].update(dev_ids)
        async_add_entities(GeofencyEntity(dev_id) for dev_id in dev_ids)

    return True


class GeofencyEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    def __init__(self, device, gps=None, location_name=None, attributes=None):
        """Set up Geofency entity."""
        self._attributes = attributes or {}
        self._name = device
        self._location_name = location_name
        self._gps = gps
        self._unsub_dispatcher = None
        self._unique_id = device

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        return self._attributes

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._gps[0]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._gps[1]

    @property
    def location_name(self):
        """Return a location name for the current location of the device."""
        return self._location_name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {"name": self._name, "identifiers": {(GF_DOMAIN, self._unique_id)}}

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    async def async_added_to_hass(self):
        """Register state update callback."""
        await super().async_added_to_hass()
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

        if self._attributes:
            return

        state = await self.async_get_last_state()

        if state is None:
            self._gps = (None, None)
            return

        attr = state.attributes
        self._gps = (attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        await super().async_will_remove_from_hass()
        self._unsub_dispatcher()
        self.hass.data[GF_DOMAIN]["devices"].remove(self._unique_id)

    @callback
    def _async_receive_data(self, device, gps, location_name, attributes):
        """Mark the device as seen."""
        if device != self.name:
            return

        self._attributes.update(attributes)
        self._location_name = location_name
        self._gps = gps
        self.async_write_ha_state()
