"""The Anglian Water integration."""

from __future__ import annotations

from aiohttp import CookieJar
from pyanglianwater import AnglianWater
from pyanglianwater.auth import MSOB2CAuth
from pyanglianwater.exceptions import (
    ExpiredAccessTokenError,
    SelfAssertedError,
    SmartMeterUnavailableError,
)

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_ACCOUNT_NUMBER, DOMAIN
from .coordinator import AnglianWaterConfigEntry, AnglianWaterUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AnglianWaterConfigEntry
) -> bool:
    """Set up Anglian Water from a config entry."""
    auth = MSOB2CAuth(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=async_create_clientsession(
            hass,
            cookie_jar=CookieJar(quote_cookie=False),
        ),
        refresh_token=entry.data[CONF_ACCESS_TOKEN],
    )
    try:
        await auth.send_refresh_request()
    except (ExpiredAccessTokenError, SelfAssertedError) as err:
        raise ConfigEntryAuthFailed from err

    _aw = AnglianWater(authenticator=auth)

    try:
        await _aw.validate_smart_meter(entry.data[CONF_ACCOUNT_NUMBER])
    except SmartMeterUnavailableError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="smart_meter_unavailable"
        ) from err

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_ACCESS_TOKEN: auth.refresh_token}
    )
    entry.runtime_data = coordinator = AnglianWaterUpdateCoordinator(
        hass=hass, api=_aw, config_entry=entry
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AnglianWaterConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
