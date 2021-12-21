"""Starlink satellite binary sensors."""

from spacex.starlink.outage_reason import OutageReason

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_DIAGNOSTIC
from homeassistant.core import HomeAssistant

from . import BaseStarlinkEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the binary sensors."""
    dish, coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [entity(coordinator, dish) for entity in StarlinkBinaryEntity.__subclasses__()]
    )

    return True


class StarlinkBinaryEntity(BaseStarlinkEntity, BinarySensorEntity):
    """The parent class of all Starlink binary sensors."""

    pass


class ConnectedEntity(StarlinkBinaryEntity):
    """Whether or not the satellite is connected."""

    base_name = "Connected"
    device_class = DEVICE_CLASS_CONNECTIVITY

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return f"{self.dish.id}.connected"

    @property
    def icon(self) -> str:
        """Return an icon representing the connection status, or whatever problem is stopping the connection."""
        if self.is_on:
            return "mdi:check-network-outline"
        elif self.dish.status.outage_reason == OutageReason.OBSTRUCTED:
            return "mdi:weather-cloudy-alert"
        elif self.dish.status.outage_reason == OutageReason.BOOTING:
            return "mdi:update"
        elif self.dish.status.outage_reason == OutageReason.NO_SCHEDULE:
            return "mdi:satellite-uplink"
        elif self.dish.status.outage_reason == OutageReason.THERMAL_SHUTDOWN:
            return "mdi:thermometer-alert"
        elif self.dish.status.outage_reason == OutageReason.STOWED:
            return "mdi:stop-circle"
        else:
            return "mdi:alert"

    @property
    def state_attributes(self):
        """Return more information about the connection."""
        return {
            "Problem": "None"
            if self.dish.status.outage_reason is None
            else self.dish.status.outage_reason.label
        }

    @property
    def is_on(self):
        """Return true if the satellite is connected."""
        return self.dish.status.connected


class ObstructedEntity(StarlinkBinaryEntity):
    """Whether or not the satellite is reporting an obstruction."""

    base_name = "Obstruction"
    device_class = DEVICE_CLASS_PROBLEM

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return f"{self.dish.id}.obstructed"

    @property
    def entity_category(self):
        """Return the category for this sensor."""
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def is_on(self):
        """Return true if the satellite is reporting an obstruction."""
        return self.dish.status.obstructed
