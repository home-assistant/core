"""Tracker for Wifi clients connected to a TP-Link EAP."""
import logging
from typing import List, Set

import async_timeout
from pytleap import Client, Eap, PytleapError

from homeassistant.components.device_tracker import (
    ATTR_MAC,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the device_tracker by config_entry."""
    coordinator = TpLinkEapCoordinator(
        hass, config_entry, async_add_entities, hass.data[DOMAIN][config_entry.entry_id]
    )

    # Initialize already tracked entities
    tracked: Set[str] = set()
    registry = await entity_registry.async_get_registry(hass)
    known_entities: List[Entity] = []
    for entity in registry.entities.values():
        if (
            entity.domain == DEVICE_TRACKER_DOMAIN
            and entity.config_entry_id == config_entry.entry_id
        ):
            tracked.add(entity.unique_id)
            known_entities.append(WifiClientEntity(coordinator, entity.unique_id))
    async_add_entities(known_entities, True)
    coordinator.tracked_entity_macs = tracked

    if not known_entities:
        # If no entities exist, need to bootstrap process
        await coordinator.async_refresh()


class TpLinkEapCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TP-Link EAP data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities,
        eap: Eap,
    ):
        """Initialize the TP-Link EAP Coordinator."""
        self.hass = hass
        self.config = config_entry
        self.async_add_entities = async_add_entities

        self.eap = eap

        self.tracked_entity_macs: Set[str] = set()
        self.connected_clients: [str, Client] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            update_method=self.async_update,
        )

    async def async_update(self):
        """Update the coordinator."""
        _LOGGER.debug("Updating connected devices")
        try:
            async with async_timeout.timeout(SCAN_INTERVAL.seconds):
                connected_clients = await self.eap.get_wifi_clients()
        except PytleapError as err:
            _LOGGER.error("Could not refresh Wifi client: %s", err)
            return

        _LOGGER.debug("Scan result: %s", connected_clients)

        new_tracked = []
        for client in connected_clients:
            mac = client.mac_address
            if mac in self.tracked_entity_macs:
                continue
            self.tracked_entity_macs.add(mac)
            new_tracked.append(WifiClientEntity(self, client.mac_address))

        _LOGGER.debug("Newly connected clients: %s", new_tracked)
        if new_tracked:
            self.async_add_entities(new_tracked, True)

        self.connected_clients = {c.mac_address: c for c in connected_clients}


class WifiClientEntity(CoordinatorEntity, ScannerEntity):
    """A class representing an EAP Wifi client device."""

    def __init__(self, coordinator: TpLinkEapCoordinator, mac: str):
        """Initialize a Wifi client entity."""
        super().__init__(coordinator)
        self.mac = mac

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.mac

    @property
    def state_attributes(self):
        """Return the device state attributes."""
        return {ATTR_MAC: self.mac.upper()}

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_ROUTER

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self.mac in self.coordinator.connected_clients
