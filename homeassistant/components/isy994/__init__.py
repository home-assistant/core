"""Support the Universal Devices ISY/IoX controllers."""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from aiohttp import CookieJar
import async_timeout
from pyisy import ISY, ISYConnectionError, ISYInvalidAuthError, ISYResponseParseError
from pyisy.constants import CONFIG_NETWORKING, CONFIG_PORTAL
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VARIABLES,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    _LOGGER,
    CONF_IGNORE_STRING,
    CONF_NETWORK,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    DEFAULT_IGNORE_STRING,
    DEFAULT_SENSOR_STRING,
    DOMAIN,
    ISY_CONF_FIRMWARE,
    ISY_CONF_MODEL,
    ISY_CONF_NAME,
    MANUFACTURER,
    PLATFORMS,
    SCHEME_HTTP,
    SCHEME_HTTPS,
)
from .helpers import _categorize_nodes, _categorize_programs
from .models import IsyData
from .services import async_setup_services, async_unload_services
from .util import _async_cleanup_registry_entries

CONFIG_SCHEMA = vol.Schema(
    cv.deprecated(DOMAIN),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up the ISY 994 integration."""
    hass.data.setdefault(DOMAIN, {})
    isy_data = hass.data[DOMAIN][entry.entry_id] = IsyData()

    isy_config = entry.data
    isy_options = entry.options

    # Required
    user = isy_config[CONF_USERNAME]
    password = isy_config[CONF_PASSWORD]
    host = urlparse(isy_config[CONF_HOST])

    # Optional
    tls_version = isy_config.get(CONF_TLS_VER)
    ignore_identifier = isy_options.get(CONF_IGNORE_STRING, DEFAULT_IGNORE_STRING)
    sensor_identifier = isy_options.get(CONF_SENSOR_STRING, DEFAULT_SENSOR_STRING)

    if host.scheme == SCHEME_HTTP:
        https = False
        port = host.port or 80
        session = aiohttp_client.async_create_clientsession(
            hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
        )
    elif host.scheme == SCHEME_HTTPS:
        https = True
        port = host.port or 443
        session = aiohttp_client.async_get_clientsession(hass)
    else:
        _LOGGER.error("The ISY/IoX host value in configuration is invalid")
        return False

    # Connect to ISY controller.
    isy = ISY(
        host.hostname,
        port,
        username=user,
        password=password,
        use_https=https,
        tls_ver=tls_version,
        webroot=host.path,
        websession=session,
        use_websocket=True,
    )

    try:
        async with async_timeout.timeout(60):
            await isy.initialize()
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(
            "Timed out initializing the ISY; device may be busy, trying again later:"
            f" {err}"
        ) from err
    except ISYInvalidAuthError as err:
        raise ConfigEntryAuthFailed(f"Invalid credentials for the ISY: {err}") from err
    except ISYConnectionError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to the ISY, please adjust settings and try again: {err}"
        ) from err
    except ISYResponseParseError as err:
        raise ConfigEntryNotReady(
            "Invalid XML response from ISY; Ensure the ISY is running the latest"
            f" firmware: {err}"
        ) from err
    except TypeError as err:
        raise ConfigEntryNotReady(
            f"Invalid response ISY, device is likely still starting: {err}"
        ) from err

    _categorize_nodes(isy_data, isy.nodes, ignore_identifier, sensor_identifier)
    _categorize_programs(isy_data, isy.programs)
    # Gather ISY Variables to be added.
    if isy.variables.children:
        isy_data.devices[CONF_VARIABLES] = _create_service_device_info(
            isy, name=CONF_VARIABLES.title(), unique_id=CONF_VARIABLES
        )
        numbers = isy_data.variables[Platform.NUMBER]
        for vtype, _, vid in isy.variables.children:
            numbers.append(isy.variables[vtype][vid])
    if (
        isy.conf[CONFIG_NETWORKING] or isy.conf[CONFIG_PORTAL]
    ) and isy.networking.nobjs:
        isy_data.devices[CONF_NETWORK] = _create_service_device_info(
            isy, name=CONFIG_NETWORKING, unique_id=CONF_NETWORK
        )
        for resource in isy.networking.nobjs:
            isy_data.net_resources.append(resource)

    # Dump ISY Clock Information. Future: Add ISY as sensor to Hass with attrs
    _LOGGER.info(repr(isy.clock))

    isy_data.root = isy
    _async_get_or_create_isy_device_in_registry(hass, entry, isy)

    # Load platforms for the devices in the ISY controller that we support.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean-up any old entities that we no longer provide.
    _async_cleanup_registry_entries(hass, entry.entry_id)

    @callback
    def _async_stop_auto_update(event: Event) -> None:
        """Stop the isy auto update on Home Assistant Shutdown."""
        _LOGGER.debug("ISY Stopping Event Stream and automatic updates")
        isy.websocket.stop()

    _LOGGER.debug("ISY Starting Event Stream and automatic updates")
    isy.websocket.start()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_auto_update)
    )

    # Register Integration-wide Services:
    async_setup_services(hass)

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_get_or_create_isy_device_in_registry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, isy: ISY
) -> None:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, isy.uuid)},
        identifiers={(DOMAIN, isy.uuid)},
        manufacturer=MANUFACTURER,
        name=isy.conf[ISY_CONF_NAME],
        model=isy.conf[ISY_CONF_MODEL],
        sw_version=isy.conf[ISY_CONF_FIRMWARE],
        configuration_url=isy.conn.url,
    )


def _create_service_device_info(isy: ISY, name: str, unique_id: str) -> DeviceInfo:
    """Create device info for ISY service devices."""
    return DeviceInfo(
        identifiers={
            (
                DOMAIN,
                f"{isy.uuid}_{unique_id}",
            )
        },
        manufacturer=MANUFACTURER,
        name=f"{isy.conf[ISY_CONF_NAME]} {name}",
        model=isy.conf[ISY_CONF_MODEL],
        sw_version=isy.conf[ISY_CONF_FIRMWARE],
        configuration_url=isy.conn.url,
        via_device=(DOMAIN, isy.uuid),
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    isy_data = hass.data[DOMAIN][entry.entry_id]

    isy: ISY = isy_data.root

    _LOGGER.debug("ISY Stopping Event Stream and automatic updates")
    isy.websocket.stop()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    async_unload_services(hass)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove ISY config entry from a device."""
    isy_data = hass.data[DOMAIN][config_entry.entry_id]
    return not device_entry.identifiers.intersection(
        (DOMAIN, unique_id) for unique_id in isy_data.devices
    )
