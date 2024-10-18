"""The Cookidoo integration."""

from __future__ import annotations

from cookidoo_api import (
    DEFAULT_COOKIDOO_CONFIG,
    Cookidoo,
    CookidooActionException,
    CookidooAuthBotDetectionException,
    CookidooAuthException,
    CookidooConfigException,
    CookidooNavigationException,
    CookidooSelectorException,
    CookidooUnavailableException,
    CookidooUnexpectedStateException,
)

from homeassistant.const import (
    CONF_EMAIL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import BROWSER_RUNNER_TIMEOUT, DOMAIN
from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Set up Cookidoo from a config entry."""

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    runner_host = entry.data[CONF_HOST]
    runner_port = entry.data[CONF_PORT]

    cookidoo = Cookidoo(
        {
            **DEFAULT_COOKIDOO_CONFIG,
            "browser": "chromium",
            "headless": True,
            "remote_addr": runner_host,
            "remote_port": runner_port,
            "network_timeout": BROWSER_RUNNER_TIMEOUT,
            "timeout": BROWSER_RUNNER_TIMEOUT,
            "load_media": False,
            "email": email,
            "password": password,
            "tracing": True,
            "screenshots": True,
        }
    )

    try:
        await cookidoo.login()
    except CookidooConfigException as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_request_exception",
        ) from e
    except (
        CookidooUnavailableException,
        CookidooNavigationException,
        CookidooSelectorException,
        CookidooActionException,
        CookidooUnexpectedStateException,
    ) as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_parse_exception",
        ) from e
    except CookidooAuthBotDetectionException as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_authentication_captcha_exception",
            translation_placeholders={CONF_EMAIL: email},
        ) from e
    except CookidooAuthException as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_authentication_exception",
            translation_placeholders={CONF_EMAIL: email},
        ) from e

    coordinator = CookidooDataUpdateCoordinator(hass, cookidoo)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
