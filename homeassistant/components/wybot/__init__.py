"""The WyBot integration."""

from wybot import WybotAuthError, WybotConnectionError, WyBotHTTPClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import WyBotCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.VACUUM]

type WyBotConfigEntry = ConfigEntry[WyBotCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WyBotConfigEntry) -> bool:
    """Set up WyBot from a config entry."""
    wybot_http_client = WyBotHTTPClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    try:
        await wybot_http_client.authenticate()
    except WybotAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except WybotConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    coordinator = WyBotCoordinator(
        hass, wybot_http_client=wybot_http_client, config_entry=entry
    )
    entry.runtime_data = coordinator

    # Register cleanup before the first refresh: that refresh can start the MQTT
    # background task, so a later setup failure must still tear it down.
    entry.async_on_unload(coordinator.async_stop)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WyBotConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
