"""The WiiM integration."""

from __future__ import annotations

from urllib.parse import urlparse

from wiim.controller import WiimController
from wiim.discovery import async_create_wiim_device
from wiim.exceptions import WiimDeviceException, WiimRequestException
from wiim.wiim_device import WiimDevice

from homeassistant.components.network import async_get_source_ip
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CONF_UDN,
    CONF_UPNP_LOCATION,
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
    if DOMAIN not in hass.data:
        session = async_get_clientsession(hass)
        wiim_controller = WiimController(session, event_callback=None)
        hass.data[DOMAIN] = WiimData(
            controller=wiim_controller,
            entity_id_to_udn_map={},
        )

    wiim_domain_data = hass.data[DOMAIN]
    controller = wiim_domain_data.controller

    host = entry.data[CONF_HOST]
    udn = entry.data[CONF_UDN]
    upnp_location = entry.data.get(CONF_UPNP_LOCATION)

    if not upnp_location:
        LOGGER.error(
            "UPnP location is missing in config entry for %s (UDN: %s, Host: %s). "
            "UPnP location is required for setup",
            entry.title,
            udn,
            host,
        )
        raise ConfigEntryNotReady(
            f"Missing UPnP location in config entry for {entry.title} (UDN: {udn})"
        )

    if upnp_location and host:
        upnp_location = upnp_location.replace(urlparse(upnp_location).hostname, host)

    wiim_device = None
    try:
        ha_host: str | None = None

        try:
            base_url = get_url(hass, prefer_external=False)
            parsed_url = urlparse(base_url)
            ha_host = parsed_url.hostname

            LOGGER.debug("Resolved HA host IP via get_url: %s", ha_host)
        except (NoURLAvailableError, ValueError, TypeError) as err:
            LOGGER.warning(
                "Could not determine HA URL via get_url, falling back: %s", err
            )
            ha_host = await async_get_source_ip(hass)

        wiim_device = await async_create_wiim_device(
            upnp_location,
            async_get_clientsession(hass),
            host=host,
            ha_host_ip=ha_host,
            polling_interval=DEFAULT_AVAILABILITY_POLLING_INTERVAL,
        )
    except WiimRequestException as err:
        LOGGER.error("HTTP API request failed during setup for %s: %s", host, err)
        raise ConfigEntryNotReady(f"HTTP API request failed for {host}: {err}") from err
    except WiimDeviceException as err:
        LOGGER.error("SDK Device Exception during setup for %s: %s", host, err)
        raise ConfigEntryNotReady(f"SDK Device error for {host}: {err}") from err
    except Exception as err:
        LOGGER.exception("Unexpected error setting up WiiM device %s: %s", host, err)
        raise ConfigEntryNotReady(f"Unexpected error for {host}: {err}") from err

    if wiim_device is None:
        raise ConfigEntryNotReady(f"Failed to initialize WiiM device at {upnp_location}")

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
        hass.data.pop(DOMAIN, None)
        LOGGER.info("Last WiiM entry unloaded, cleaning up domain data")
    return True
