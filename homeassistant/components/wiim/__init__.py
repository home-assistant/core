# homeassistant/components/wiim/__init__.py
"""The WiiM integration."""

from __future__ import annotations

import socket
from urllib.parse import urlparse

from aiohttp import ClientSession, TCPConnector
from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client import UpnpDevice
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpConnectionError, UpnpError
from wiim.controller import WiimController
from wiim.endpoint import WiimApiEndpoint
from wiim.exceptions import WiimDeviceException, WiimRequestException
from wiim.wiim_device import WiimDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_UDN,
    CONF_UPNP_LOCATION,
    DEFAULT_AVAILABILITY_POLLING_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SDK_LOGGER,
    WiimData,
)

type WiimConfigEntry = ConfigEntry


def _get_local_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


async def async_setup_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> bool:
    """Set up WiiM from a config entry (called after async_setup or UI flow)."""
    SDK_LOGGER.debug(
        "Setting up WiiM entry: %s (UDN: %s, Source: %s)",
        entry.title,
        entry.data.get(CONF_UDN),
        entry.source,
    )

    # Ensure domain data is initialized (could be set by async_setup or another entry)
    if DOMAIN not in hass.data:
        session = async_get_clientsession(hass)
        wiim_controller = WiimController(session, event_callback=None)
        hass.data[DOMAIN] = WiimData(
            controller=wiim_controller,
            entity_id_to_udn_map={},
        )

    wiim_domain_data = hass.data[DOMAIN]
    controller = wiim_domain_data.controller
    controller.session = async_get_clientsession(hass)

    host = entry.data[CONF_HOST]
    udn = entry.data[CONF_UDN]
    upnp_location = entry.data.get(CONF_UPNP_LOCATION)

    session = async_get_clientsession(hass)
    requester = AiohttpRequester(timeout=10)
    upnp_device_instance: UpnpDevice | None = None
    wiim_device_sdk: WiimDevice | None = None

    if upnp_location and host:
        upnp_location = upnp_location.replace(urlparse(upnp_location).hostname, host)

    try:
        if upnp_location:
            SDK_LOGGER.debug(
                "Attempting to create UpnpDevice for %s from location: %s",
                entry.title,
                upnp_location,
            )
            try:
                factory = UpnpFactory(requester)
                upnp_device_instance = await factory.async_create_device(upnp_location)
                SDK_LOGGER.debug(
                    "Successfully created UpnpDevice: %s",
                    upnp_device_instance.friendly_name,
                )
            except (TimeoutError, UpnpConnectionError, UpnpError) as err:
                SDK_LOGGER.warning(
                    "Failed to create UpnpDevice from location %s for %s: %s",
                    upnp_location,
                    entry.title,
                    err,
                )
                raise ConfigEntryNotReady(
                    f"Failed to connect to UPnP device at {upnp_location}: {err}"
                ) from err
        else:
            SDK_LOGGER.warning(
                "UPnP location not found in config entry for %s (UDN: %s, Host: %s). "
                "WiiM device will attempt to initialize; UPnP eventing might be unavailable or delayed.",
                entry.title,
                udn,
                host,
            )

            return False

        sessions = ClientSession(connector=TCPConnector(ssl=False))
        http_api = WiimApiEndpoint(
            protocol="https", port=443, endpoint=host, session=sessions
        )
        ha_host_ip = None

        if hass.config.internal_url:
            if isinstance(hass.config.internal_url, str) and hass.config.internal_url:
                try:
                    parsed_url = urlparse(hass.config.internal_url)
                    if parsed_url.hostname:
                        ha_host_ip = parsed_url.hostname
                        SDK_LOGGER.debug(
                            "Using internal_url hostname as HA host IP: %s", ha_host_ip
                        )
                except ValueError:
                    SDK_LOGGER.warning(
                        "Invalid internal_url configured: %s", hass.config.internal_url
                    )
        elif hass.config.external_url:
            if isinstance(hass.config.external_url, str) and hass.config.external_url:
                try:
                    parsed_url = urlparse(hass.config.external_url)
                    if parsed_url.hostname:
                        ha_host_ip = parsed_url.hostname
                        SDK_LOGGER.debug(
                            "Using external_url hostname as HA host IP: %s", ha_host_ip
                        )
                except ValueError:
                    SDK_LOGGER.warning(
                        "Invalid external_url configured: %s", hass.config.external_url
                    )

        if not ha_host_ip:
            ha_host_ip = await hass.async_add_executor_job(_get_local_ip)
            if ha_host_ip:
                SDK_LOGGER.debug(
                    "Using socket fallback to determine HA host IP: %s", ha_host_ip
                )
            else:
                SDK_LOGGER.error(
                    "Failed to determine Home Assistant host IP using socket fallback"
                )

        wiim_device_sdk = WiimDevice(
            upnp_device=upnp_device_instance,
            session=session,
            http_api_endpoint=http_api,
            ha_host_ip=ha_host_ip,
            polling_interval=DEFAULT_AVAILABILITY_POLLING_INTERVAL,
        )

        await controller.add_device(wiim_device_sdk)

        entry.runtime_data = wiim_device_sdk
        SDK_LOGGER.info(
            "WiiM device %s (UDN: %s) linked to HASS. Name: '%s', HTTP: %s, UPnP Location: %s",
            entry.entry_id,
            wiim_device_sdk.udn,
            wiim_device_sdk.name,
            host,
            upnp_location or "N/A",
        )

    except ConfigEntryNotReady:
        if wiim_device_sdk:
            await wiim_device_sdk.disconnect()
        raise
    except WiimRequestException as err:
        if wiim_device_sdk:
            await wiim_device_sdk.disconnect()
        SDK_LOGGER.error("HTTP API request failed during setup for %s: %s", host, err)
        raise ConfigEntryNotReady(f"HTTP API request failed for {host}: {err}") from err
    except WiimDeviceException as err:
        if wiim_device_sdk:
            await wiim_device_sdk.disconnect()
        SDK_LOGGER.error("SDK Device Exception during setup for %s: %s", host, err)
        raise ConfigEntryNotReady(f"SDK Device error for {host}: {err}") from err
    except Exception as err:
        if wiim_device_sdk:
            await wiim_device_sdk.disconnect()
        SDK_LOGGER.exception(
            "Unexpected error setting up WiiM device %s: %s", host, err
        )
        raise ConfigEntryNotReady(f"Unexpected error for {host}: {err}") from err

    async def _async_shutdown_event_handler(event: Event) -> None:
        SDK_LOGGER.info(
            "Home Assistant stopping, disconnecting WiiM device: %s",
            wiim_device_sdk.name,
        )
        await wiim_device_sdk.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_shutdown_event_handler
        )
    )

    # entry.async_on_unload(wiim_device_sdk.disconnect)
    # Unload function to remove from controller and disconnect
    async def _unload_entry_cleanup():
        SDK_LOGGER.debug("Running unload cleanup for %s", wiim_device_sdk.name)
        await controller.remove_device(wiim_device_sdk.udn)
        await wiim_device_sdk.disconnect()

    entry.async_on_unload(_unload_entry_cleanup)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> bool:
    """Unload a config entry."""
    SDK_LOGGER.info(
        "Unloading WiiM entry: %s (UDN: %s)", entry.title, entry.data.get(CONF_UDN)
    )

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        wiim_domain_data = hass.data.get(DOMAIN)
        if wiim_domain_data:
            udn_to_remove = entry.data.get(CONF_UDN)
            if udn_to_remove:
                keys_to_del = [
                    entity_id
                    for entity_id, udn in wiim_domain_data.entity_id_to_udn_map.items()
                    if udn == udn_to_remove
                ]
                for key in keys_to_del:
                    del wiim_domain_data.entity_id_to_udn_map[key]
                    SDK_LOGGER.debug(
                        "Removed %s from entity_id_to_udn_map during unload.", key
                    )

        remaining_entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not remaining_entries:
            hass.data.pop(DOMAIN, None)
            SDK_LOGGER.info("Last WiiM entry unloaded, cleaning up domain data.")
    return unload_ok
