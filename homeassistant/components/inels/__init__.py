"""The iNels integration."""
from __future__ import annotations

from typing import Any

from homewizard_energy import RequestError
from inelsmqtt import InelsMqtt
from inelsmqtt.devices import Device
from inelsmqtt.discovery import InelsDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.device_registry as dr

from .const import (
    BROKER,
    COORDINATOR,
    COORDINATOR_LIST,
    DOMAIN,
    LOGGER,
    STARTUP_MESSAGE,
)
from .coordinator import InelsDeviceUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iNels from a config entry."""
    LOGGER.info(STARTUP_MESSAGE)

    inels_data: dict[str, Any] = {}

    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = inels_data

    d_e = entry.data

    mqtt: InelsMqtt = await hass.async_add_executor_job(
        InelsMqtt,
        d_e[CONF_HOST],
        d_e[CONF_PORT],
        d_e[CONF_USERNAME] if d_e[CONF_USERNAME] is not None else None,
        d_e[CONF_PASSWORD] if d_e[CONF_PASSWORD] is not None else None,
    )

    async def on_hass_stop(event: Event) -> None:
        """Close connection when hass stops."""
        await hass.async_add_executor_job(mqtt.disconnect)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    try:
        i_disc = InelsDiscovery(mqtt)
        devices: list[Device] = await hass.async_add_executor_job(i_disc.discovery())
    except RequestError as exc:
        await hass.async_add_executor_job(mqtt.disconnect)
        raise ConfigEntryNotReady from exc

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={(DOMAIN, entry.data[""])},
        manufacturer="Elko EP s.r.o.",
        name="iNELS",
        model="",
    )

    coordinator_data = {BROKER: mqtt, COORDINATOR_LIST: []}

    for device in devices:
        coordinator = InelsDeviceUpdateCoordinator(hass=hass, device=device)
        await coordinator.async_config_entry_first_refresh()

        coordinator_data[COORDINATOR_LIST].append(coordinator)

    inels_data[COORDINATOR] = coordinator_data
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
