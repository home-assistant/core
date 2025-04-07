"""Support for August devices."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from aiohttp import ClientResponseError
from yalexs.const import Brand
from yalexs.exceptions import AugustApiAIOHTTPError
from yalexs.manager.exceptions import CannotConnect, InvalidAuth, RequireValidation
from yalexs.manager.gateway import Config as YaleXSConfig

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import DOMAIN, PLATFORMS
from .data import AugustData
from .gateway import AugustGateway
from .util import async_create_august_clientsession

type AugustConfigEntry = ConfigEntry[AugustData]


@callback
def _async_create_yale_brand_migration_issue(
    hass: HomeAssistant, entry: AugustConfigEntry
) -> None:
    """Create an issue for a brand migration."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "yale_brand_migration",
        breaks_in_ha_version="2024.9",
        learn_more_url="https://www.home-assistant.io/integrations/yale",
        translation_key="yale_brand_migration",
        is_fixable=False,
        severity=ir.IssueSeverity.CRITICAL,
        translation_placeholders={
            "migrate_url": "https://my.home-assistant.io/redirect/config_flow_start?domain=yale"
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: AugustConfigEntry) -> bool:
    """Set up August from a config entry."""
    session = async_create_august_clientsession(hass)
    august_gateway = AugustGateway(Path(hass.config.config_dir), session)
    try:
        await async_setup_august(hass, entry, august_gateway)
    except (RequireValidation, InvalidAuth) as err:
        raise ConfigEntryAuthFailed from err
    except TimeoutError as err:
        raise ConfigEntryNotReady("Timed out connecting to august api") from err
    except (AugustApiAIOHTTPError, ClientResponseError, CannotConnect) as err:
        raise ConfigEntryNotReady from err
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: AugustConfigEntry) -> None:
    """Remove an August config entry."""
    ir.async_delete_issue(hass, DOMAIN, "yale_brand_migration")


async def async_unload_entry(hass: HomeAssistant, entry: AugustConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_setup_august(
    hass: HomeAssistant, entry: AugustConfigEntry, august_gateway: AugustGateway
) -> None:
    """Set up the August component."""
    config = cast(YaleXSConfig, entry.data)
    await august_gateway.async_setup(config)
    if august_gateway.api.brand == Brand.YALE_HOME:
        _async_create_yale_brand_migration_issue(hass, entry)
    await august_gateway.async_authenticate()
    await august_gateway.async_refresh_access_token_if_needed()
    data = entry.runtime_data = AugustData(hass, august_gateway)
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, data.async_stop)
    )
    entry.async_on_unload(data.async_stop)
    await data.async_setup()


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: AugustConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove august config entry from a device if its no longer present."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and config_entry.runtime_data.get_device(identifier[1])
    )
