"""Support the ISY-994 controllers."""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from aiohttp import CookieJar
import async_timeout
from pyisy import ISY, ISYConnectionError, ISYInvalidAuthError, ISYResponseParseError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    _LOGGER,
    CONF_IGNORE_STRING,
    CONF_RESTORE_LIGHT_STATE,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    CONF_VAR_SENSOR_STRING,
    DEFAULT_IGNORE_STRING,
    DEFAULT_RESTORE_LIGHT_STATE,
    DEFAULT_SENSOR_STRING,
    DEFAULT_VAR_SENSOR_STRING,
    DOMAIN,
    ISY994_ISY,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_VARIABLES,
    MANUFACTURER,
    PLATFORMS,
    PROGRAM_PLATFORMS,
    SENSOR_AUX,
)
from .helpers import _categorize_nodes, _categorize_programs, _categorize_variables
from .services import async_setup_services, async_unload_services
from .util import unique_ids_for_config_entry_id

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.url,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TLS_VER): vol.Coerce(float),
                vol.Optional(
                    CONF_IGNORE_STRING, default=DEFAULT_IGNORE_STRING
                ): cv.string,
                vol.Optional(
                    CONF_SENSOR_STRING, default=DEFAULT_SENSOR_STRING
                ): cv.string,
                vol.Optional(
                    CONF_VAR_SENSOR_STRING, default=DEFAULT_VAR_SENSOR_STRING
                ): cv.string,
                vol.Required(
                    CONF_RESTORE_LIGHT_STATE, default=DEFAULT_RESTORE_LIGHT_STATE
                ): bool,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the isy994 integration from YAML."""
    isy_config: ConfigType | None = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not isy_config:
        return True

    # Only import if we haven't before.
    config_entry = _async_find_matching_config_entry(hass)
    if not config_entry:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=dict(isy_config),
            )
        )
        return True

    # Update the entry based on the YAML configuration, in case it changed.
    hass.config_entries.async_update_entry(config_entry, data=dict(isy_config))
    return True


@callback
def _async_find_matching_config_entry(
    hass: HomeAssistant,
) -> config_entries.ConfigEntry | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.source == config_entries.SOURCE_IMPORT:
            return entry
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up the ISY 994 integration."""
    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options
    _async_import_options_from_data_if_missing(hass, entry)

    hass.data[DOMAIN][entry.entry_id] = {}
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]

    hass_isy_data[ISY994_NODES] = {SENSOR_AUX: []}
    for platform in PLATFORMS:
        hass_isy_data[ISY994_NODES][platform] = []

    hass_isy_data[ISY994_PROGRAMS] = {}
    for platform in PROGRAM_PLATFORMS:
        hass_isy_data[ISY994_PROGRAMS][platform] = []

    hass_isy_data[ISY994_VARIABLES] = []

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
    variable_identifier = isy_options.get(
        CONF_VAR_SENSOR_STRING, DEFAULT_VAR_SENSOR_STRING
    )

    if host.scheme == "http":
        https = False
        port = host.port or 80
        session = aiohttp_client.async_create_clientsession(
            hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
        )
    elif host.scheme == "https":
        https = True
        port = host.port or 443
        session = aiohttp_client.async_get_clientsession(hass)
    else:
        _LOGGER.error("The isy994 host value in configuration is invalid")
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
            f"Timed out initializing the ISY; device may be busy, trying again later: {err}"
        ) from err
    except ISYInvalidAuthError as err:
        raise ConfigEntryAuthFailed(f"Invalid credentials for the ISY: {err}") from err
    except ISYConnectionError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to the ISY, please adjust settings and try again: {err}"
        ) from err
    except ISYResponseParseError as err:
        raise ConfigEntryNotReady(
            f"Invalid XML response from ISY; Ensure the ISY is running the latest firmware: {err}"
        ) from err
    except TypeError as err:
        raise ConfigEntryNotReady(
            f"Invalid response ISY, device is likely still starting: {err}"
        ) from err

    _categorize_nodes(hass_isy_data, isy.nodes, ignore_identifier, sensor_identifier)
    _categorize_programs(hass_isy_data, isy.programs)
    _categorize_variables(hass_isy_data, isy.variables, variable_identifier)

    # Dump ISY Clock Information. Future: Add ISY as sensor to Hass with attrs
    _LOGGER.info(repr(isy.clock))

    hass_isy_data[ISY994_ISY] = isy
    _async_get_or_create_isy_device_in_registry(hass, entry, isy)

    # Load platforms for the devices in the ISY controller that we support.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    options = dict(entry.options)
    modified = False
    for importable_option in (
        CONF_IGNORE_STRING,
        CONF_SENSOR_STRING,
        CONF_RESTORE_LIGHT_STATE,
    ):
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            modified = True

    if modified:
        hass.config_entries.async_update_entry(entry, options=options)


@callback
def _async_isy_to_configuration_url(isy: ISY) -> str:
    """Extract the configuration url from the isy."""
    connection_info = isy.conn.connection_info
    proto = "https" if "tls" in connection_info else "http"
    return f"{proto}://{connection_info['addr']}:{connection_info['port']}"


@callback
def _async_get_or_create_isy_device_in_registry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, isy: ISY
) -> None:
    device_registry = dr.async_get(hass)
    url = _async_isy_to_configuration_url(isy)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, isy.configuration["uuid"])},
        identifiers={(DOMAIN, isy.configuration["uuid"])},
        manufacturer=MANUFACTURER,
        name=isy.configuration["name"],
        model=isy.configuration["model"],
        sw_version=isy.configuration["firmware"],
        configuration_url=url,
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass_isy_data = hass.data[DOMAIN][entry.entry_id]

    isy: ISY = hass_isy_data[ISY994_ISY]

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
    """Remove isy994 config entry from a device."""
    return not device_entry.identifiers.intersection(
        (DOMAIN, unique_id)
        for unique_id in unique_ids_for_config_entry_id(hass, config_entry.entry_id)
    )
