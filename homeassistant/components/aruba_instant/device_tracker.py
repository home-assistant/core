import logging
import async_timeout
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for Aruba Instant component."""
    _LOGGER.debug(f"Setting up the Aruba Instant device tracker.")
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
                clients = await virtual_controller.async_update_clients()
            return clients
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = InstantCoordinator(hass, config_entry.entry_id)
    await coordinator.async_refresh()
    # hass.data[DOMAIN]['unsub_device_tracker'][config_entry.entry_id].add(tuple(coordinator.data.keys()))
    async_add_entities(
        (
            InstantClientEntity(coordinator, idx, ent)
            for idx, ent in enumerate(coordinator.data)
        ),
        True,
    )


def add_devices(instant, config_entry, device_registry):
    """Add APs into HA as devices."""
    _LOGGER.debug(f"Adding APs to the device registry.")
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


class InstantCoordinator(DataUpdateCoordinator):
    """Class to manage data updates from Aruba Instant."""

    _LOGGER.debug(f"Initializing InstantCoordinator.")

    def __init__(self, hass: HomeAssistant, entry_id):
        """Initialize Instant Coordinator."""
        self.virtual_controller = hass.data[DOMAIN][entry_id]

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )

    def update_listeners(self) -> None:
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def _async_update_data(self):
        """Update data from Aruba Instant."""
        clients = await self.virtual_controller.async_update_clients()
        return clients


class InstantClientEntity(ScannerEntity):
    """Instant Client Entity"""

    def __init__(self, coordinator, idx, ent):
        _LOGGER.debug(f"Creating entity for client {ent}.")
        self.coordinator = coordinator
        self.hass = self.coordinator.hass
        self.idx = idx
        self._mac = ent
        # self.entity_id = f"instant_{self._mac}"
        self._name = coordinator.data[self._mac].get("name")
        self._ip = coordinator.data[self._mac].get("ip")
        self._mac = coordinator.data[self._mac].get("mac")
        self._os = coordinator.data[self._mac].get("os")
        self._essid = coordinator.data[self._mac].get("essid")
        self._ap = coordinator.data[self._mac].get("ap")
        self._channel = coordinator.data[self._mac].get("channel")
        self._phy = coordinator.data[self._mac].get("phy")
        self._role = coordinator.data[self._mac].get("role")
        self._ipv6 = coordinator.data[self._mac].get("ipv6")
        self._signal = coordinator.data[self._mac].get("signal")
        self._signal_text = coordinator.data[self._mac].get("signal_text")
        self._speed = coordinator.data[self._mac].get("speed")
        self._speed_text = coordinator.data[self._mac].get("speed_text")
        self._is_connected = True

    def update_entity(self):
        """Update entity data."""
        # _LOGGER.debug(f"Updating info for client {self._mac}")
        try:
            self._name = self.coordinator.data[self._mac].get("name")
            self._ip = self.coordinator.data[self._mac].get("ip")
            self._mac = self.coordinator.data[self._mac].get("mac")
            self._os = self.coordinator.data[self._mac].get("os")
            self._essid = self.coordinator.data[self._mac].get("essid")
            self._ap = self.coordinator.data[self._mac].get("ap")
            self._channel = self.coordinator.data[self._mac].get("channel")
            self._phy = self.coordinator.data[self._mac].get("phy")
            self._role = self.coordinator.data[self._mac].get("role")
            self._ipv6 = self.coordinator.data[self._mac].get("ipv6")
            self._signal = self.coordinator.data[self._mac].get("signal")
            self._signal_text = self.coordinator.data[self._mac].get("signal_text")
            self._speed = self.coordinator.data[self._mac].get("speed")
            self._speed_text = self.coordinator.data[self._mac].get("speed_text")
            self._is_connected = True
        except KeyError as error:
            _LOGGER.debug(f"{self._mac} - {self._name} is no longer connected.")
            self._is_connected = False

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

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    @property
    def is_connected(self):
        """Return the status of a client on the network."""
        # TODO research a way to determine status
        return self._is_connected

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
    def device_state_attributes(self) -> dict:
        """Return device info."""
        self.update_entity()
        return {
            "name": self._name,
            "ip": self._ip,
            "mac": self._mac,
            "os": self._os,
            "essid": self._essid,
            "ap": self._ap,
            "channel": self._channel,
            "phy": self._phy,
            "role": self._role,
            "ipv6": self._ipv6,
            "signal": self._signal,
            "signal_text": self._signal_text,
            "speed": self._speed,
            "speed_text": self._speed_text,
        }
