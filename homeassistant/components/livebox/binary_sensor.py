"""Livebox binary sensor entities."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)

from .const import COORDINATOR, DOMAIN, LIVEBOX_ID, TEMPLATE_SENSOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer binary sensor setup to the shared sensor module."""
    datas = hass.data[DOMAIN][config_entry.entry_id]
    box_id = datas[LIVEBOX_ID]
    coordinator = datas[COORDINATOR]
    async_add_entities([WanStatus(coordinator, box_id)], True)


class WanStatus(BinarySensorEntity):
    """Representation of a livebox sensor."""

    device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(self, coordinator, box_id):
        """Initialize the sensor."""
        self.box_id = box_id
        self.coordinator = coordinator

    @property
    def name(self):
        """Return name sensor."""
        return f"{TEMPLATE_SENSOR} Wan status"

    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.coordinator.data["wan_status"].get("status")

    @property
    def unique_id(self):
        """Return unique_id."""
        return f"{self.box_id}_connectivity"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": TEMPLATE_SENSOR,
            "via_device": (DOMAIN, self.box_id),
        }

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            "link_type": self.coordinator.data["wan_status"]
            .get("data", {})
            .get("LinkType"),
            "link_state": self.coordinator.data["wan_status"]
            .get("data", {})
            .get("LinkState"),
            "last_connection_error": self.coordinator.data["wan_status"]
            .get("data", {})
            .get("LastConnectionError"),
            "wan_ipaddress": self.coordinator.data["wan_status"]
            .get("data", {})
            .get("IPAddress"),
            "wan_ipv6address": self.coordinator.data["wan_status"]
            .get("data", {})
            .get("IPv6Address"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self) -> None:
        """Update WLED entity."""
        await self.coordinator.async_request_refresh()
