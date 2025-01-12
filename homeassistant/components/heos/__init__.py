"""Denon HEOS Media Player."""

from __future__ import annotations

import logging

from pyheos import Credentials, Heos, HeosError, HeosOptions

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import services
from .const import DOMAIN
from .coordinator import (
    ControllerManager,
    GroupManager,
    HeosConfigEntry,
    HeosRuntimeData,
    SourceManager,
)

PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HEOS component."""
    services.register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HeosConfigEntry) -> bool:
    """Initialize config entry which represents the HEOS controller."""
    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    # Migrate non-string device identifiers.
    device_registry = dr.async_get(hass)
    for device in device_registry.devices.get_devices_for_config_entry_id(
        entry.entry_id
    ):
        for domain, player_id in device.identifiers:
            if domain == DOMAIN and not isinstance(player_id, str):
                device_registry.async_update_device(
                    device.id, new_identifiers={(DOMAIN, str(player_id))}
                )
            break

    host = entry.data[CONF_HOST]
    credentials: Credentials | None = None
    if entry.options:
        credentials = Credentials(
            entry.options[CONF_USERNAME], entry.options[CONF_PASSWORD]
        )

    # Setting all_progress_events=False ensures that we only receive a
    # media position update upon start of playback or when media changes
    controller = Heos(
        HeosOptions(
            host,
            all_progress_events=False,
            auto_reconnect=True,
            credentials=credentials,
        )
    )

    # Auth failure handler must be added before connecting to the host, otherwise
    # the event will be missed when login fails during connection.
    async def auth_failure() -> None:
        """Handle authentication failure."""
        entry.async_start_reauth(hass)

    entry.async_on_unload(controller.add_on_user_credentials_invalid(auth_failure))

    try:
        # Auto reconnect only operates if initial connection was successful.
        await controller.connect()
    except HeosError as error:
        await controller.disconnect()
        _LOGGER.debug("Unable to connect to controller %s: %s", host, error)
        raise ConfigEntryNotReady from error

    # Disconnect when shutting down
    async def disconnect_controller(event):
        await controller.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_controller)
    )

    # Get players and sources
    try:
        players = await controller.get_players()
        favorites = {}
        if controller.is_signed_in:
            favorites = await controller.get_favorites()
        else:
            _LOGGER.warning(
                "The HEOS System is not logged in: Enter credentials in the integration options to access favorites and streaming services"
            )
        inputs = await controller.get_input_sources()
    except HeosError as error:
        await controller.disconnect()
        _LOGGER.debug("Unable to retrieve players and sources: %s", error)
        raise ConfigEntryNotReady from error

    controller_manager = ControllerManager(hass, controller)
    await controller_manager.connect_listeners()

    source_manager = SourceManager(favorites, inputs)
    source_manager.connect_update(hass, controller)

    group_manager = GroupManager(hass, controller, players)

    entry.runtime_data = HeosRuntimeData(
        controller_manager, group_manager, source_manager, players
    )

    group_manager.connect_update()
    entry.async_on_unload(group_manager.disconnect_update)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeosConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.controller_manager.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
