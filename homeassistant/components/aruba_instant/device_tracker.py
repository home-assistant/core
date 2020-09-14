"""Aruba Instant Device Tracker"""

from datetime import timedelta
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, DISCOVERED_DEVICES, TRACKED_DEVICES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for Aruba Instant component."""
    _LOGGER.debug("Setting up the Aruba Instant device tracker.")
    device_registry = await dr.async_get_registry(hass)
    virtual_controller = hass.data[DOMAIN][config_entry.entry_id]
    await virtual_controller.async_setup()
    add_devices(virtual_controller, config_entry, device_registry)

    coordinator = InstantCoordinator(hass, config_entry, async_add_entities)
    await coordinator.async_refresh()
    async_add_entities(
        InstantClientEntity(coordinator, client)
        for client in config_entry.data["clients"]
    )
    hass.data[DOMAIN]["coordinator"] = {config_entry.entry_id: coordinator}


def add_devices(instant, config_entry, device_registry):
    """Add APs into HA as devices."""
    _LOGGER.debug("Adding APs to the device registry.")
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

    _LOGGER.debug("Initializing InstantCoordinator.")

    def __init__(self, hass: HomeAssistant, config_entry, async_add_entities):
        """Initialize Instant Coordinator."""
        self.async_add_entities = async_add_entities
        self.config_entry = config_entry
        self.virtual_controller = hass.data[DOMAIN][config_entry.entry_id]
        self.entities = {}
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=config_entry.data.get("scan_interval")),
        )

    def update_listeners(self) -> None:
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def _async_update_data(self) -> dict:
        """Update data from Aruba Instant."""
        clients = await self.virtual_controller.async_update_clients()
        for client in clients:
            self.hass.data[DOMAIN][DISCOVERED_DEVICES][self.config_entry.entry_id].add(
                client
            )
        return clients


class InstantClientEntity(ScannerEntity):
    """Instant Client Entity"""

    def __init__(self, coordinator, ent):
        _LOGGER.debug(f"Creating entity for client {ent}.")
        self.coordinator = coordinator
        self.hass = self.coordinator.hass
        self._mac = ent
        try:
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
            self._lat = self.coordinator.hass.config.latitude
            self._lon = self.coordinator.hass.config.longitude
            self._is_connected = True
            self.coordinator.entities.update({self.unique_id: self})
        except KeyError:
            _LOGGER.debug(f"{self._mac} is not currently connected.")
            self._is_connected = False
            self._name = "Unknown"
            self._ip = None
            self._os = None
            self._essid = None
            self._ap = None
            self._channel = None
            self._phy = None
            self._role = None
            self._ipv6 = None
            self._signal = None
            self._signal_text = None
            self._speed = None
            self._speed_text = None
            self._lat = None
            self._lon = None

    def update_entity(self) -> None:
        """Update entity data."""
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
            self._lat = self.coordinator.hass.config.latitude
            self._lon = self.coordinator.hass.config.longitude
            if self._is_connected is False:
                _LOGGER.debug(f"{self._mac} - {self._name} is now connected.")
            self._is_connected = True
        except KeyError:
            if self._is_connected is True:
                _LOGGER.debug(f"{self._mac} - {self._name} is no longer connected.")
            self._is_connected = False
            self._ip = None
            self._os = None
            self._essid = None
            self._ap = None
            self._channel = None
            self._phy = None
            self._role = None
            self._ipv6 = None
            self._signal = None
            self._signal_text = None
            self._speed = None
            self._speed_text = None
            self._lat = None
            self._lon = None

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        if (
            self.unique_id
            in self.hass.data[DOMAIN][TRACKED_DEVICES][
                self.coordinator.virtual_controller.entry_id
            ]
        ):
            return True
        return False

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    @property
    def is_connected(self) -> bool:
        """Return the status of a client on the network."""
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
            "latitude": self._lat,
            "longitude": self._lon,
        }
