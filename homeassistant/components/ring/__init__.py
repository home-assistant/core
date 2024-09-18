"""Support for Ring Doorbell/Chimes."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, cast
import uuid

from ring_doorbell import Auth, Ring, RingDevices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import APPLICATION_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    instance_id,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LISTEN_CREDENTIALS, DOMAIN, PLATFORMS
from .coordinator import RingDataCoordinator, RingListenCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class RingData:
    """Class to support type hinting of ring data collection."""

    api: Ring
    devices: RingDevices
    devices_coordinator: RingDataCoordinator
    listen_coordinator: RingListenCoordinator


type RingConfigEntry = ConfigEntry[RingData]


async def get_auth_agent_id(hass: HomeAssistant) -> tuple[str, str]:
    """Return user-agent and hardware id for Auth instantiation.

    user_agent will be the display name in the ring.com authorised devices.
    hardware_id will uniquely describe the authorised HA device.
    """
    user_agent = f"{APPLICATION_NAME}/{DOMAIN}-integration"

    # Generate a new uuid from the instance_uuid to keep the HA one private
    instance_uuid = uuid.UUID(hex=await instance_id.async_get(hass))
    hardware_id = str(uuid.uuid5(instance_uuid, user_agent))
    return user_agent, hardware_id


async def async_setup_entry(hass: HomeAssistant, entry: RingConfigEntry) -> bool:
    """Set up a config entry."""

    def token_updater(token: dict[str, Any]) -> None:
        """Handle from async context when token is updated."""
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_TOKEN: token},
        )

    def listen_credentials_updater(token: dict[str, Any]) -> None:
        """Handle from async context when token is updated."""
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_LISTEN_CREDENTIALS: token},
        )

    user_agent, hardware_id = await get_auth_agent_id(hass)
    client_session = async_get_clientsession(hass)
    auth = Auth(
        user_agent,
        entry.data[CONF_TOKEN],
        token_updater,
        hardware_id=hardware_id,
        http_client_session=client_session,
    )
    ring = Ring(auth)

    await _migrate_old_unique_ids(hass, entry.entry_id)

    devices_coordinator = RingDataCoordinator(hass, ring)
    listen_credentials = entry.data.get(CONF_LISTEN_CREDENTIALS)
    listen_coordinator = RingListenCoordinator(
        hass, ring, listen_credentials, listen_credentials_updater
    )

    await devices_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = RingData(
        api=ring,
        devices=ring.devices(),
        devices_coordinator=devices_coordinator,
        listen_coordinator=listen_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ring entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


async def _migrate_old_unique_ids(hass: HomeAssistant, entry_id: str) -> None:
    entity_registry = er.async_get(hass)

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        # Old format for camera and light was int
        unique_id = cast(str | int, entity_entry.unique_id)
        if isinstance(unique_id, int):
            new_unique_id = str(unique_id)
            if existing_entity_id := entity_registry.async_get_entity_id(
                entity_entry.domain, entity_entry.platform, new_unique_id
            ):
                _LOGGER.error(
                    "Cannot migrate to unique_id '%s', already exists for '%s', "
                    "You may have to delete unavailable ring entities",
                    new_unique_id,
                    existing_entity_id,
                )
                return None
            _LOGGER.debug("Fixing non string unique id %s", entity_entry.unique_id)
            return {"new_unique_id": new_unique_id}
        return None

    await er.async_migrate_entries(hass, entry_id, _async_migrator)
