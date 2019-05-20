"""Code to set up a device tracker platform using a config entry."""
from typing import Optional

from homeassistant.helpers.typing import GPSType
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.const import (
    STATE_NOT_HOME,
    STATE_HOME,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_BATTERY_LEVEL,
)
from homeassistant.components import zone

from .const import (
    ATTR_SOURCE_TYPE,
    DOMAIN,
    LOGGER,
    SOURCE_TYPE_GPS,
)


async def async_setup_entry(hass, entry):
    """Set up an entry."""
    component = hass.data.get(DOMAIN)  # type: Optional[EntityComponent]

    if component is None:
        component = hass.data[DOMAIN] = EntityComponent(
            LOGGER, DOMAIN, hass
        )

    return await component.async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload an entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class DeviceTrackerEntity(Entity):
    """Represent a tracked device."""

    @property
    def battery_level(self):
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return None

    @property
    def location_accuracy(self):
        """Return the location accuracy of the device.

        Value in meters.
        """
        return 0

    @property
    def location_name(self) -> str:
        """Return a location name for the current location of the device."""
        return None

    @property
    def location(self) -> GPSType:
        """Return location value of the device."""
        # For MVP, we will only support location based devices.
        return NotImplementedError

    @property
    def mac_address(self):
        """Return the mac address of the device."""
        return None

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        raise NotImplementedError

    @property
    def state(self):
        """Return the state of the device."""
        if self.location_name:
            return self.location_name

        location = self.location

        if self.location is not None and self.source_type == SOURCE_TYPE_GPS:
            zone_state = zone.async_active_zone(
                self.hass, location[0], location[1], self.location_accuracy)
            if zone_state is None:
                state = STATE_NOT_HOME
            elif zone_state.entity_id == zone.ENTITY_ID_HOME:
                state = STATE_HOME
            else:
                state = zone_state.name
            return state

    @property
    def state_attributes(self):
        """Return the device state attributes."""
        attr = {
            ATTR_SOURCE_TYPE: self.source_type
        }

        location = self.location

        if location is not None:
            attr[ATTR_LATITUDE] = self.location[0]
            attr[ATTR_LONGITUDE] = self.location[1]
            attr[ATTR_GPS_ACCURACY] = self.location_accuracy

        if self.battery_level:
            attr[ATTR_BATTERY_LEVEL] = self.battery_level

        return attr

    @property
    def unique_id(self):
        """Return a unique ID for the device."""
        return self.mac_address
