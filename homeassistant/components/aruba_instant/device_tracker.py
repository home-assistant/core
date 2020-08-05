import logging

from typing import Dict
import async_timeout
from datetime import timedelta

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for Aruba Instant component."""
    device_registry = await dr.async_get_registry(hass)
    virtual_controller = hass.data[DOMAIN][config_entry.entry_id]
    await virtual_controller.async_setup()
    add_devices(virtual_controller, config_entry, device_registry)

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            async with async_timeout.timeout(10):
                return await virtual_controller.async_update_clients()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="aruba_instant_tracker",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )
    await coordinator.async_refresh()
    async_add_entities(
        (
            InstantClientEntity(coordinator, idx, ent)
            for idx, ent in enumerate(coordinator.data)
        ),
        True,
    )


def add_devices(instant, config_entry, device_registry):
    """Add APs into HA as devices."""
    access_points = instant.aps
    for ap in access_points:
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, access_points[ap]["ip"])},
            identifiers={(DOMAIN, access_points[ap]["serial"])},
            manufacturer="Aruba Networks",
            name=access_points[ap]["name"],
            model=access_points[ap]["type"],
        )


class InstantClientEntity(ScannerEntity):
    """Instant Client Entity"""
    def __init__(self, coordinator, idx, ent):
        self.coordinator = coordinator
        self.idx = idx
        self._mac = ent
        self._name = coordinator.data[self._mac].get("name")
        self._ip = coordinator.data[self._mac].get("ip")
        self._mac = coordinator.data[self._mac].get("mac")
        self._os = coordinator.data[self._mac].get("os")
        self._essid = coordinator.data[self._mac].get("essid")
        self._channel = coordinator.data[self._mac].get("channel")
        self._phy = coordinator.data[self._mac].get("phy")
        self._role = coordinator.data[self._mac].get("role")
        self._ipv6 = coordinator.data[self._mac].get("ipv6")
        self._signal = coordinator.data[self._mac].get("signal")
        self._signal_text = coordinator.data[self._mac].get("signal_text")
        self._speed = coordinator.data[self._mac].get("speed")
        self._speed_text = coordinator.data[self._mac].get("speed_text")

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_turn_on(self, **kwargs):
        """Turn the light on.

        Example method how to request data updates.
        """

        await self.coordinator.async_request_refresh()

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    @property
    def is_connected(self):
        """Return the status of a client on the network."""
        # TODO research a way to determine status
        return True

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def unique_id(self) -> str:
        """Return client mac address as unique id."""
        return self._mac

    @property
    def name(self) -> str:
        """Return name of client."""
        return self._name

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return device info."""
        return {
            "name": self._name,
            "ip": self._ip,
            "mac": self._mac,
            "os": self._os,
            "essid": self._essid,
            "channel": self._channel,
            "phy": self._phy,
            "role": self._role,
            "ipv6": self._ipv6,
            "signal": self._signal,
            "signal_text": self._signal_text,
            "speed": self._speed,
            "speed_text": self._speed_text,
        }
