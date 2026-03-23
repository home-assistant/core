"""The WiiM integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from wiim.controller import WiimController
from wiim.discovery import async_create_wiim_device
from wiim.exceptions import WiimDeviceException, WiimRequestException

from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DATA_WIIM, DOMAIN, LOGGER, PLATFORMS, UPNP_PORT, WiimConfigEntry
from .models import WiimData

DEFAULT_AVAILABILITY_POLLING_INTERVAL = 60


async def async_setup_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> bool:
    """Set up WiiM from a config entry.

    This method owns the device connect/disconnect lifecycle.
    """
    LOGGER.debug(
        "Setting up WiiM entry: %s (UDN: %s, Source: %s)",
        entry.title,
        entry.unique_id,
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
    upnp_location = f"http://{host}:{UPNP_PORT}/description.xml"

    try:
        base_url = get_url(hass, prefer_external=False)
    except NoURLAvailableError as err:
        raise ConfigEntryNotReady("Failed to determine Home Assistant URL") from err

    local_host = urlparse(base_url).hostname
    if TYPE_CHECKING:
        assert local_host is not None

    try:
        wiim_device = await async_create_wiim_device(
            upnp_location,
            session,
            host=host,
            local_host=local_host,
            polling_interval=DEFAULT_AVAILABILITY_POLLING_INTERVAL,
        )
    except WiimRequestException as err:
        raise ConfigEntryNotReady(f"HTTP API request failed for {host}: {err}") from err
    except WiimDeviceException as err:
        raise ConfigEntryNotReady(f"Device setup failed for {host}: {err}") from err

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
    LOGGER.info("Unloading WiiM entry: %s (UDN: %s)", entry.title, entry.unique_id)

    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        hass.data.pop(DATA_WIIM)
        LOGGER.info("Last WiiM entry unloaded, cleaning up domain data")
    return True
