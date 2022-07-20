"""The iNels integration."""
from __future__ import annotations

from typing import Any

from inelsmqtt import InelsMqtt
from inelsmqtt.devices import Device
from inelsmqtt.discovery import InelsDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    BROKER,
    BROKER_CONFIG,
    COORDINATOR_LIST,
    DOMAIN,
    LOGGER,
    STARTUP_MESSAGE,
)
from .coordinator import InelsDeviceUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Call when config entry being updated."""

    client: InelsMqtt = hass.data[BROKER]

    await hass.async_add_executor_job(client.disconnect)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iNels from a config entry."""
    if CONF_HOST not in entry.data:
        LOGGER.error("MQTT broker is not configured")
        return False

    LOGGER.info(STARTUP_MESSAGE)

    inels_data: dict[str, Any] = {
        BROKER_CONFIG: entry.data,
    }

    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = inels_data

    mqtt: InelsMqtt = await hass.async_add_executor_job(
        InelsMqtt, inels_data[BROKER_CONFIG]
    )

    inels_data[BROKER] = mqtt

    async def on_hass_stop(event: Event) -> None:
        """Close connection when hass stops."""
        await hass.async_add_executor_job(inels_data[BROKER].disconnect)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    if await hass.async_add_executor_job(inels_data[BROKER].test_connection) is False:
        return False

    try:
        i_disc = InelsDiscovery(inels_data[BROKER])
        await hass.async_add_executor_job(i_disc.discovery)

        devices: list[Device] = i_disc.devices
    except Exception as exc:
        await hass.async_add_executor_job(mqtt.close)
        raise ConfigEntryNotReady from exc

    inels_data[COORDINATOR_LIST] = []

    for device in devices:
        coordinator = InelsDeviceUpdateCoordinator(hass=hass, device=device)
        inels_data[COORDINATOR_LIST].append(coordinator)

    hass.data[DOMAIN][entry.entry_id] = inels_data
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
