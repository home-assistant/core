"""Support for AVM Fritz!Box functions."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_FRITZ,
    DEFAULT_SSL,
    DOMAIN,
    FRITZ_AUTH_EXCEPTIONS,
    FRITZ_EXCEPTIONS,
    PLATFORMS,
    SERVICE_SET_GUEST_WIFI_PW,
)
from .coordinator import AvmWrapper, FritzData

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SCHEMA_SET_GUEST_WIFI_PW = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Optional("password"): vol.Length(min=8, max=63),
        vol.Optional("length"): vol.Range(min=8, max=63),
    }
)

SERVICE_LIST: list[tuple[str, vol.Schema | None]] = [
    (SERVICE_SET_GUEST_WIFI_PW, SERVICE_SCHEMA_SET_GUEST_WIFI_PW),
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up fritzboxtools services."""
    for service, _ in SERVICE_LIST:
        if hass.services.has_service(DOMAIN, service):
            return True

    async def async_call_fritz_service(service_call: ServiceCall) -> None:
        """Call correct Fritz service."""

        target_entry_ids = await async_extract_config_entry_ids(hass, service_call)
        target_entries = [
            loaded_entry
            for loaded_entry in hass.config_entries.async_loaded_entries(DOMAIN)
            if loaded_entry.entry_id in target_entry_ids
        ]

        if not target_entries:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_found",
                translation_placeholders={"service": service_call.service},
            )

        for target_entry in target_entries:
            _LOGGER.debug("Executing service %s", service_call.service)
            avm_wrapper: AvmWrapper = hass.data[DOMAIN][target_entry.entry_id]
            await avm_wrapper.service_fritzbox(service_call, target_entry)

    for service, schema in SERVICE_LIST:
        hass.services.async_register(DOMAIN, service, async_call_fritz_service, schema)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up fritzboxtools from config entry."""
    _LOGGER.debug("Setting up FRITZ!Box Tools component")
    avm_wrapper = AvmWrapper(
        hass=hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        use_tls=entry.data.get(CONF_SSL, DEFAULT_SSL),
    )

    try:
        await avm_wrapper.async_setup(entry.options)
    except FRITZ_AUTH_EXCEPTIONS as ex:
        raise ConfigEntryAuthFailed from ex
    except FRITZ_EXCEPTIONS as ex:
        raise ConfigEntryNotReady from ex

    if (
        "X_AVM-DE_UPnP1" in avm_wrapper.connection.services
        and not (await avm_wrapper.async_get_upnp_configuration())["NewEnable"]
    ):
        raise ConfigEntryAuthFailed("Missing UPnP configuration")

    await avm_wrapper.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = avm_wrapper

    if DATA_FRITZ not in hass.data:
        hass.data[DATA_FRITZ] = FritzData()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Load the other platforms like switch
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload FRITZ!Box Tools config entry."""
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    fritz_data = hass.data[DATA_FRITZ]
    fritz_data.tracked.pop(avm_wrapper.unique_id)

    if not bool(fritz_data.tracked):
        hass.data.pop(DATA_FRITZ)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    if entry.options:
        await hass.config_entries.async_reload(entry.entry_id)
