"""Support for Mikrotik routers as device tracker."""
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.dt as dt_util

from .const import ATTR_MANUFACTURER, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for Mikrotik component."""
    mikrotik = hass.data[DOMAIN][config_entry.entry_id]

    tracked = {}

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Restore clients that is not a part of active clients list.
    for entity in entity_registry.entities.values():

        if (
            entity.config_entry_id == config_entry.entry_id
            and entity.domain == DEVICE_TRACKER
            and entity.unique_id not in mikrotik.clients
        ):

            mikrotik.restore_client(entity.unique_id)

    @callback
    def update_hub():
        """Update the status of the device."""
        update_items(mikrotik, async_add_entities, tracked)

    mikrotik.listeners.append(
        async_dispatcher_connect(hass, mikrotik.signal_data_update, update_hub)
    )

    update_hub()


@callback
def update_items(mikrotik, async_add_entities, tracked):
    """Update tracked device state from the hub."""
    new_tracked = []
    for mac, device in mikrotik.clients.items():
        if mac not in tracked:
            tracked[mac] = MikrotikHubTracker(device, mikrotik)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


class MikrotikHubTracker(ScannerEntity):
    """Representation of network device."""

    def __init__(self, device, mikrotik):
        """Initialize the tracked device."""
        self.device = device
        self.mikrotik = mikrotik
        self.hub_id = self.device.hub_id

    @property
    def is_connected(self) -> bool:
        """Return true if the client is connected to the network."""
        if (
            self.device.last_seen
            and (dt_util.utcnow() - self.device.last_seen)
            < self.mikrotik.option_detection_time
        ):
            return True
        return False

    @property
    def source_type(self) -> str:
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return self.device.name

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self.device.mac

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self.mikrotik.available

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self) -> dict:
        """Return the device state attributes."""
        return self.device.attrs

    @property
    def device_info(self):
        """Return a client description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self.device.mac)},
            "manufacturer": ATTR_MANUFACTURER,
            "identifiers": {(DOMAIN, self.device.mac)},
            "name": self.name,
            "via_device": (DOMAIN, self.device.hub_id),
        }
        return info

    async def async_update_hub_id(self):
        """Update the entity's hub ID if it has changed."""

        if not self.device.hub_id or self.hub_id == self.device.hub_id:
            return

        self.hub_id = self.device.hub_id
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        hub_device = device_registry.async_get_device({(DOMAIN, self.hub_id)}, set())
        this_device = device_registry.async_get_device(
            {(DOMAIN, self.device.mac)}, set()
        )
        if hub_device and this_device:
            _LOGGER.debug("Updating via_device_id for %s", self.name)
            device_registry.async_update_device(
                this_device.id, via_device_id=hub_device.id
            )

    async def async_added_to_hass(self):
        """Client entity created."""
        _LOGGER.debug("New network device tracker %s (%s)", self.name, self.unique_id)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.mikrotik.signal_update_clients,
                self._async_update_state,
            )
        )

    # @callback
    # async def _async_set_update_interval(self):
    #     """Set device update interval."""

    #     async def async_update(event_time=None):
    #         """Update client state."""
    #         await self._async_update_state()

    #     if self.unsub_timer is not None:
    #         self.unsub_timer()
    #     self.unsub_timer = async_track_time_interval(
    #         self.hass, async_update, self.mikrotik.option_detection_time
    #     )

    #     await async_update()

    @callback
    async def _async_update_state(self):
        """Update device state and related hub_id."""
        _LOGGER.debug(
            "Updating Mikrotik tracked client %s (%s)", self.entity_id, self.unique_id,
        )
        await self.async_update_hub_id()
        self.async_write_ha_state()

    # async def async_will_remove_from_hass(self):
    #     """Remove device if no other linked entities exist."""
    #     if self.unsub_timer:
    #         self.unsub_timer()
