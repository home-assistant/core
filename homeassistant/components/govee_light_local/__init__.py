"""The Govee Light local integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
import logging

from govee_local_api.controller import LISTENING_PORT

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_AUTO_DISCOVERY,
    CONF_IPS_TO_REMOVE,
    CONF_MANUAL_DEVICES,
    DISCOVERY_TIMEOUT,
    SIGNAL_GOVEE_DEVICE_REMOVE,
)
from .coordinator import (
    GoveeLocalApiConfig,
    GoveeLocalApiCoordinator,
    GoveeLocalConfigEntry,
    OptionMode,
)

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> bool:
    """Set up Govee light local from a config entry."""
    coordinator = GoveeLocalApiCoordinator(hass, entry)

    async def await_cleanup():
        cleanup_complete: asyncio.Event = coordinator.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup_complete.wait(), 1)

    entry.async_on_unload(await_cleanup)
    entry.async_on_unload(entry.add_update_listener(update_options_listener))

    if entry.options and CONF_MANUAL_DEVICES in entry.options:
        for device in entry.options[CONF_MANUAL_DEVICES]:
            coordinator.add_device_to_discovery_queue(device)

    try:
        await coordinator.start()
    except OSError as ex:
        if ex.errno != EADDRINUSE:
            _LOGGER.error("Start failed, errno: %d", ex.errno)
            return False
        _LOGGER.error("Port %s already in use", LISTENING_PORT)
        raise ConfigEntryNotReady from ex

    await coordinator.async_config_entry_first_refresh()

    if entry.data.get(CONF_AUTO_DISCOVERY, True):
        try:
            async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
                while not coordinator.devices:
                    await asyncio.sleep(delay=1)
        except TimeoutError as ex:
            raise ConfigEntryNotReady from ex

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def update_options_listener(
    hass: HomeAssistant, config_entry: GoveeLocalConfigEntry
) -> None:
    """Handle options update."""
    coordinator: GoveeLocalApiCoordinator = config_entry.runtime_data
    config: GoveeLocalApiConfig = GoveeLocalApiConfig.from_config_entry(config_entry)

    if config.option_mode == OptionMode.ADD_DEVICE and config.manual_devices:
        for ip in config.manual_devices:
            if coordinator.get_device_by_ip(ip) is None:
                coordinator.add_device_to_discovery_queue(ip)

    if config.option_mode == OptionMode.REMOVE_DEVICE and config.ips_to_remove:
        for ip in config.ips_to_remove:
            if device := coordinator.get_device_by_ip(ip):
                async_dispatcher_send(
                    hass, SIGNAL_GOVEE_DEVICE_REMOVE, device.fingerprint
                )
            coordinator.remove_device_from_discovery_queue(ip)
            config_entry.options[CONF_IPS_TO_REMOVE].remove(ip)
            config_entry.options[CONF_MANUAL_DEVICES].remove(ip)

    if (
        config.option_mode == OptionMode.CONFIGURE_AUTO_DISCOVERY
        and coordinator.discovery_enabled != config.auto_discovery
    ):
        coordinator.enable_discovery(config.auto_discovery)


async def async_unload_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
