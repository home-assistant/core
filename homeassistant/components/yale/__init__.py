"""Support for Yale devices."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from aiohttp import ClientResponseError
from yalexs.const import Brand
from yalexs.exceptions import YaleApiError
from yalexs.manager.const import CONF_BRAND
from yalexs.manager.exceptions import CannotConnect, InvalidAuth, RequireValidation
from yalexs.manager.gateway import Config as YaleXSConfig

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr

from .const import DOMAIN, PLATFORMS
from .data import YaleData
from .gateway import YaleGateway
from .util import async_create_yale_clientsession

type YaleConfigEntry = ConfigEntry[YaleData]


async def async_setup_entry(hass: HomeAssistant, entry: YaleConfigEntry) -> bool:
    """Set up yale from a config entry."""
    session = async_create_yale_clientsession(hass)
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    yale_gateway = YaleGateway(Path(hass.config.config_dir), session, oauth_session)
    try:
        await async_setup_yale(hass, entry, yale_gateway)
    except (RequireValidation, InvalidAuth) as err:
        raise ConfigEntryAuthFailed from err
    except TimeoutError as err:
        raise ConfigEntryNotReady("Timed out connecting to yale api") from err
    except (YaleApiError, ClientResponseError, CannotConnect) as err:
        raise ConfigEntryNotReady from err
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: YaleConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_setup_yale(
    hass: HomeAssistant, entry: YaleConfigEntry, yale_gateway: YaleGateway
) -> None:
    """Set up the yale component."""
    config = cast(YaleXSConfig, entry.data)
    await yale_gateway.async_setup({**config, CONF_BRAND: Brand.YALE_GLOBAL})
    await yale_gateway.async_authenticate()
    await yale_gateway.async_refresh_access_token_if_needed()
    data = entry.runtime_data = YaleData(hass, yale_gateway)
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, data.async_stop)
    )
    entry.async_on_unload(data.async_stop)
    await data.async_setup()


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: YaleConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove yale config entry from a device if its no longer present."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and config_entry.runtime_data.get_device(identifier[1])
    )
