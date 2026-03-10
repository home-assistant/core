"""The WiiM integration."""

from __future__ import annotations

from urllib.parse import urlparse

from wiim.controller import WiimController
from wiim.discovery import async_create_wiim_device
from wiim.exceptions import WiimDeviceException, WiimRequestException
from wiim.wiim_device import WiimDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CONF_UDN,
    CONF_UPNP_LOCATION,
    DATA_WIIM,
    DEFAULT_AVAILABILITY_POLLING_INTERVAL,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    WiimData,
)

type WiimConfigEntry = ConfigEntry[WiimDevice]


async def async_setup_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> bool:
    """Set up WiiM from a config entry (called after async_setup or UI flow)."""
    LOGGER.debug(
        "Setting up WiiM entry: %s (UDN: %s, Source: %s)",
        entry.title,
        entry.data.get(CONF_UDN),
        entry.source,
    )

    # This integration maintains shared domain-level state because:
    # - Multiple config entries can be loaded simultaneously.
    # - All WiiM devices share a single WiimController instance
    #   to coordinate network communication and event handling.
    # - We also maintain a global entity_id -> UDN mapping
    #   used for cross-entity event routing.
    #
    # The domain data must therefore be initialized once and reused
    # across all config entries.
    session = async_get_clientsession(hass)

    if DATA_WIIM not in hass.data:
        hass.data[DATA_WIIM] = WiimData(controller=WiimController(session))

    wiim_domain_data = hass.data[DATA_WIIM]
    controller = wiim_domain_data.controller

    host = entry.data[CONF_HOST]
    upnp_location = entry.data[CONF_UPNP_LOCATION]
    upnp_location_host = urlparse(upnp_location).hostname

    if upnp_location_host is None:
        raise ConfigEntryNotReady(f"Invalid WiiM UPnP location: {upnp_location}")

    upnp_location = upnp_location.replace(upnp_location_host, host)

    try:
        base_url = get_url(hass, prefer_external=False)
        local_host = urlparse(base_url).hostname
    except (NoURLAvailableError, ValueError, TypeError) as err:
        raise ConfigEntryNotReady(
            "Failed to determine Home Assistant URL for WiiM event subscriptions"
        ) from err

    if local_host is None:
        raise ConfigEntryNotReady(
            "Home Assistant URL does not include a hostname for WiiM event subscriptions"
        )

    try:
        wiim_device = await async_create_wiim_device(
            upnp_location,
            session,
            host=host,
            local_host=local_host,
            polling_interval=DEFAULT_AVAILABILITY_POLLING_INTERVAL,
        )
    except WiimRequestException as err:
        LOGGER.error("HTTP API request failed during setup for %s: %s", host, err)
        raise ConfigEntryNotReady(f"HTTP API request failed for {host}: {err}") from err
    except WiimDeviceException as err:
        LOGGER.error("SDK Device Exception during setup for %s: %s", host, err)
        raise ConfigEntryNotReady(f"SDK Device error for {host}: {err}") from err

    await controller.add_device(wiim_device)

    entry.runtime_data = wiim_device
    LOGGER.info(
        "WiiM device %s (UDN: %s) linked to HASS. Name: '%s', HTTP: %s, UPnP Location: %s",
        entry.entry_id,
        wiim_device.udn,
        wiim_device.name,
        host,
        upnp_location or "N/A",
    )

    async def _async_shutdown_event_handler(event: Event) -> None:
        LOGGER.info(
            "Home Assistant stopping, disconnecting WiiM device: %s",
            wiim_device.name,
        )
        await wiim_device.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_shutdown_event_handler
        )
    )

    async def _unload_entry_cleanup():
        """Cleanup when unloading the config entry.

        Removes the device from the controller and disconnects it.
        """
        LOGGER.debug("Running unload cleanup for %s", wiim_device.name)
        await controller.remove_device(wiim_device.udn)
        await wiim_device.disconnect()

    entry.async_on_unload(_unload_entry_cleanup)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.info(
        "Unloading WiiM entry: %s (UDN: %s)", entry.title, entry.data.get(CONF_UDN)
    )

    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        hass.data.pop(DATA_WIIM, None)
        LOGGER.info("Last WiiM entry unloaded, cleaning up domain data")
    return True
