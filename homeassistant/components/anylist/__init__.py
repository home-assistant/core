"""The AnyList integration."""

from typing import cast

from aioanylist import AnyListClient, AuthTokens

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_REFRESH_TOKEN, CONF_USER_LOCALE, DOMAIN
from .coordinator import AnyListConfigEntry, AnyListDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AnyList integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AnyListConfigEntry) -> bool:
    """Set up AnyList from a config entry."""

    @callback
    def token_updater(tokens: AuthTokens | None) -> None:
        """Persist rotated AnyList tokens."""
        if tokens is None:
            return

        data = {
            **entry.data,
            CONF_ACCESS_TOKEN: tokens.access_token,
            CONF_REFRESH_TOKEN: tokens.refresh_token,
        }
        if tokens.user_locale:
            data[CONF_USER_LOCALE] = tokens.user_locale
        hass.config_entries.async_update_entry(entry, data=data)

    tokens = AuthTokens(
        user_id=cast(str, entry.unique_id),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        user_locale=entry.data.get(CONF_USER_LOCALE),
    )
    client = AnyListClient(
        async_get_clientsession(hass),
        tokens=tokens,
        user_email=entry.data[CONF_EMAIL],
        client_id=entry.data[CONF_CLIENT_ID],
        token_callback=token_updater,
    )

    coordinator = AnyListDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AnyListConfigEntry) -> bool:
    """Unload an AnyList config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
