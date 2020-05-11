"""Support for Mikrotik routers as device tracker."""
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
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

    @callback
    def update_hub():
        """Update the status of the device."""
        update_items(mikrotik, async_add_entities, tracked)

    mikrotik.unsub_listener = async_dispatcher_connect(
        hass, mikrotik.signal_new_clients, update_hub
    )

    update_hub()


@callback
def update_items(mikrotik, async_add_entities, tracked):
    """Update tracked device state from the hub."""
    new_tracked = []
    for mac, client in mikrotik.clients.items():
        if mac not in tracked:
            tracked[mac] = MikrotikHubTracker(client, mikrotik)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


class MikrotikHubTracker(ScannerEntity):
    """Representation of network device."""

    def __init__(self, client, mikrotik):
        """Initialize the tracked device."""
        self.client = client
        self.mikrotik = mikrotik
        self.host = self.client.host
        self.this_device = None

    @property
    def is_connected(self) -> bool:
        """Return true if the client is connected to the network."""
        if (
            self.client.last_seen
            and (dt_util.utcnow() - self.client.last_seen)
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
        return self.client.name

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self.client.mac

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
        return self.client.attrs

    @property
    def device_info(self):
        """Return a client description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self.client.mac)},
            "manufacturer": ATTR_MANUFACTURER,
            "identifiers": {(DOMAIN, self.client.mac)},
            "name": self.name,
            "via_device": (DOMAIN, self.client.host),
        }
        return info

    async def async_update_via_device_id(self):
        """Update the device details if it has changed."""

        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        hub_device = device_registry.async_get_device(
            {(DOMAIN, self.client.host)}, set()
        )
        if not hub_device:
            return

        _LOGGER.debug("Updating via_device_id for %s", self.name)
        if not self.this_device:
            self.this_device = device_registry.async_get_device(
                {(DOMAIN, self.client.mac)}, set()
            )
        device_registry.async_update_device(
            self.this_device.id, via_device_id=hub_device.id
        )
        self.host = self.client.host

    async def async_added_to_hass(self):
        """Client entity created."""
        _LOGGER.debug("New network device tracker %s (%s)", self.name, self.unique_id)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.mikrotik.signal_data_update, self._async_update_state,
            )
        )

    @callback
    async def _async_update_state(self):
        """Update device state and related hub_id."""
        _LOGGER.debug(
            "Updating Mikrotik tracked client %s (%s)", self.entity_id, self.unique_id,
        )
        if self.client.host and self.host != self.client.host:
            await self.async_update_via_device_id()
        self.async_write_ha_state()
