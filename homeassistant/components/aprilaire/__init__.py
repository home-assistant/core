"""The Aprilaire integration."""

from __future__ import annotations

import logging
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .const import DOMAIN, LOG_NAME
from .coordinator import AprilaireCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, **kwargs) -> bool:
    """Set up a config entry for Aprilaire."""

    logger = cast(logging.Logger, kwargs.get("logger"))

    if not logger:  # pragma: no cover
        logger = logging.getLogger(LOG_NAME)  # pragma: no cover

    config = entry.data

    host = config.get(CONF_HOST)
    if host is None or len(host) == 0:
        logger.error("Invalid host %s", host)
        return False

    port = config.get(CONF_PORT)
    if port is None or port <= 0:
        logger.error("Invalid port %s", port)
        return False

    coordinator = AprilaireCoordinator(hass, host, port, logger)
    await coordinator.start_listen()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def ready_callback(ready: bool):
        if ready:
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

            async def _async_close(_: Event) -> None:
                coordinator.stop_listen()  # pragma: no cover

            entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)
            )
        else:
            logger.error("Failed to wait for ready")

            coordinator.stop_listen()

    await coordinator.wait_for_ready(ready_callback)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: AprilaireCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.stop_listen()

    return unload_ok
