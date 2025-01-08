"""Support for Ring Doorbell/Chimes."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, cast
import uuid

from ring_doorbell import Auth, Ring, RingDevices

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import APPLICATION_NAME, CONF_DEVICE_ID, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
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


def get_auth_user_agent() -> str:
    """Return user-agent for Auth instantiation.

    user_agent will be the display name in the ring.com authorised devices.
    """
    return f"{APPLICATION_NAME}/{DOMAIN}-integration"


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

    user_agent = get_auth_user_agent()
    client_session = async_get_clientsession(hass)
    auth = Auth(
        user_agent,
        entry.data[CONF_TOKEN],
        token_updater,
        hardware_id=entry.data[CONF_DEVICE_ID],
        http_client_session=client_session,
    )
    ring = Ring(auth)

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry."""
    entry_version = entry.version
    entry_minor_version = entry.minor_version
    entry_id = entry.entry_id

    new_minor_version = 2
    if entry_version == 1 and entry_minor_version == 1:
        _LOGGER.debug(
            "Migrating from version %s.%s", entry_version, entry_minor_version
        )
        # Migrate non-str unique ids
        # This step used to run unconditionally from async_setup_entry
        entity_registry = er.async_get(hass)

        @callback
        def _async_str_unique_id_migrator(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
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

        await er.async_migrate_entries(hass, entry_id, _async_str_unique_id_migrator)

        # Migrate the hardware id
        hardware_id = str(uuid.uuid4())
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_DEVICE_ID: hardware_id},
            minor_version=new_minor_version,
        )
        _LOGGER.debug(
            "Migration to version %s.%s complete", entry_version, new_minor_version
        )

    entry_minor_version = entry.minor_version
    new_minor_version = 3
    if entry_version == 1 and entry_minor_version == 2:
        _LOGGER.debug(
            "Migrating from version %s.%s", entry_version, entry_minor_version
        )

        @callback
        def _async_camera_unique_id_migrator(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
            # Migrate camera unique ids to append -last
            if entity_entry.domain == CAMERA_DOMAIN and not isinstance(
                cast(str | int, entity_entry.unique_id), int
            ):
                new_unique_id = f"{entity_entry.unique_id}-last_recording"
                return {"new_unique_id": new_unique_id}
            return None

        await er.async_migrate_entries(hass, entry_id, _async_camera_unique_id_migrator)

        hass.config_entries.async_update_entry(
            entry,
            minor_version=new_minor_version,
        )
        _LOGGER.debug(
            "Migration to version %s.%s complete", entry_version, new_minor_version
        )

    return True
