"""Code to set up a device tracker platform using a config entry."""
from __future__ import annotations

from typing import final

from homeassistant.components import zone
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import StateType

from .const import ATTR_HOST_NAME, ATTR_IP, ATTR_MAC, ATTR_SOURCE_TYPE, DOMAIN, LOGGER


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an entry."""
    component: EntityComponent | None = hass.data.get(DOMAIN)

    if component is None:
        component = hass.data[DOMAIN] = EntityComponent(LOGGER, DOMAIN, hass)

    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class BaseTrackerEntity(Entity):
    """Represent a tracked device."""

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return None

    @property
    def source_type(self) -> str:
        """Return the source type, eg gps or router, of the device."""
        raise NotImplementedError

    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the device state attributes."""
        attr: dict[str, StateType] = {ATTR_SOURCE_TYPE: self.source_type}

        if self.battery_level is not None:
            attr[ATTR_BATTERY_LEVEL] = self.battery_level

        return attr


class TrackerEntity(BaseTrackerEntity):
    """Base class for a tracked device."""

    @property
    def should_poll(self) -> bool:
        """No polling for entities that have location pushed."""
        return False

    @property
    def force_update(self) -> bool:
        """All updates need to be written to the state machine if we're not polling."""
        return not self.should_poll

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device.

        Value in meters.
        """
        return 0

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        raise NotImplementedError

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        raise NotImplementedError

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self.location_name is not None:
            return self.location_name

        if self.latitude is not None and self.longitude is not None:
            zone_state = zone.async_active_zone(
                self.hass, self.latitude, self.longitude, self.location_accuracy
            )
            if zone_state is None:
                state = STATE_NOT_HOME
            elif zone_state.entity_id == zone.ENTITY_ID_HOME:
                state = STATE_HOME
            else:
                state = zone_state.name
            return state

        return None

    @final
    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the device state attributes."""
        attr: dict[str, StateType] = {}
        attr.update(super().state_attributes)
        if self.latitude is not None and self.longitude is not None:
            attr[ATTR_LATITUDE] = self.latitude
            attr[ATTR_LONGITUDE] = self.longitude
            attr[ATTR_GPS_ACCURACY] = self.location_accuracy

        return attr


class ScannerEntity(BaseTrackerEntity):
    """Base class for a tracked device that is on a scanned network."""

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return None

    @property
    def mac_address(self) -> str | None:
        """Return the mac address of the device."""
        return None

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return None

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self.is_connected:
            return STATE_HOME
        return STATE_NOT_HOME

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        raise NotImplementedError

    @final
    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the device state attributes."""
        attr: dict[str, StateType] = {}
        attr.update(super().state_attributes)
        if self.ip_address is not None:
            attr[ATTR_IP] = self.ip_address
        if self.mac_address is not None:
            attr[ATTR_MAC] = self.mac_address
        if self.hostname is not None:
            attr[ATTR_HOST_NAME] = self.hostname

        return attr
