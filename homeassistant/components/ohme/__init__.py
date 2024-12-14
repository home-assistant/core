"""Set up ohme integration."""

from ohme import ApiException, AuthException, OhmeApiClient

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .coordinator import (
    OhmeAdvancedSettingsCoordinator,
    OhmeChargeSessionCoordinator,
    OhmeConfigEntry,
)


async def async_setup_entry(hass: HomeAssistant, entry: OhmeConfigEntry) -> bool:
    """Set up Ohme from a config entry."""

    client = OhmeApiClient(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    try:
        await client.async_login()

        if not await client.async_update_device_info():
            raise ConfigEntryNotReady(
                translation_key="device_info_failed", translation_domain=DOMAIN
            )
    except AuthException as e:
        raise ConfigEntryError(
            translation_key="auth_failed", translation_domain=DOMAIN
        ) from e
    except ApiException as e:
        raise ConfigEntryNotReady(
            translation_key="api_failed", translation_domain=DOMAIN
        ) from e

    coordinators = [
        OhmeChargeSessionCoordinator(hass, entry, client),
        OhmeAdvancedSettingsCoordinator(hass, entry, client),
    ]

    for coordinator in coordinators:
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OhmeConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
