"""The ecosmart integration."""

from aioecosmart import (
    EcosmartAuthError,
    EcosmartClient,
    EcosmartError,
    EcosmartRateLimitError,
)

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER
from .coordinator import EcosmartConfigEntry, EcosmartCoordinator, retry_delay
from .services import async_setup_services

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ecosmart service actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EcosmartConfigEntry) -> None:
    """Set up ecosmart from a config entry."""
    client = EcosmartClient(entry.data[CONF_API_KEY], async_get_clientsession(hass))

    try:
        identity = await client.me()
    except EcosmartAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except EcosmartRateLimitError as err:
        retry_after = retry_delay(err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="rate_limited",
            translation_placeholders={"retry_after": str(retry_after)},
            retry_after=retry_after,
        ) from err
    except EcosmartError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    LOGGER.debug(
        "ecosmart key %s covers %s ICP(s) with a budget of %s requests/minute",
        identity.key_prefix,
        len(identity.allowed_icps),
        identity.rate_limit_per_minute,
    )

    coordinator = EcosmartCoordinator(hass, entry, client, identity)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: EcosmartConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
