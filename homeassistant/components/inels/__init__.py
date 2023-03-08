"""The iNels integration."""
from __future__ import annotations

from typing import Any

from inelsmqtt import InelsMqtt
from inelsmqtt.discovery import InelsDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import BROKER, BROKER_CONFIG, DEVICES, DOMAIN, LOGGER

PLATFORMS: list[Platform] = [
    Platform.COVER,
]


async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Call when config entry being updated."""

    client: InelsMqtt = hass.data[BROKER]

    await hass.async_add_executor_job(client.disconnect)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iNels from a config entry."""

    if CONF_HOST not in entry.data:
        LOGGER.error("MQTT broker is not configured")
        return False

    inels_data: dict[str, Any] = {
        BROKER_CONFIG: entry.data,
    }

    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = inels_data

    mqtt: InelsMqtt = await hass.async_add_executor_job(
        InelsMqtt, inels_data[BROKER_CONFIG]
    )

    inels_data[BROKER] = mqtt

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    if await hass.async_add_executor_job(inels_data[BROKER].test_connection) is False:
        return False

    try:
        i_disc = InelsDiscovery(inels_data[BROKER])
        await hass.async_add_executor_job(i_disc.discovery)

        inels_data[DEVICES] = i_disc.devices
    except Exception as exc:
        await hass.async_add_executor_job(mqtt.close)
        raise ConfigEntryNotReady from exc

    LOGGER.info("Finished discovery, setting up platforms")

    hass.data[DOMAIN][entry.entry_id] = inels_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOGGER.info("Platform setup complete")
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload all devices."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    broker: InelsMqtt = hass_data[BROKER]

    broker.unsubscribe_listeners()
    broker.disconnect()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    if hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True
