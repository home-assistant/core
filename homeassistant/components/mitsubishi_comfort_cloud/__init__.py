"""The Mitsubishi Comfort Cloud integration."""

import asyncio
import logging

from mitsubishi_comfort import CloudIndoorUnit, MitsubishiCloudAccount
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .coordinator import (
    MitsubishiComfortCloudConfigEntry,
    MitsubishiComfortCloudCoordinator,
)
from .helpers import async_discover_devices

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: MitsubishiComfortCloudConfigEntry
) -> None:
    """Set up Mitsubishi Comfort Cloud from a config entry."""
    account = MitsubishiCloudAccount(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    try:
        await account.login()
        devices = await async_discover_devices(account)
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err
    except DeviceConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    if not devices:
        raise ConfigEntryError(translation_domain=DOMAIN, translation_key="no_devices")

    coordinators = {
        serial: MitsubishiComfortCloudCoordinator(
            hass, entry, CloudIndoorUnit(info, account)
        )
        for serial, info in devices.items()
    }
    results = await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        ),
        return_exceptions=True,
    )
    failures: list[ConfigEntryNotReady | ConfigEntryAuthFailed] = []
    auth_failure: ConfigEntryAuthFailed | None = None
    for result in results:
        if isinstance(result, ConfigEntryAuthFailed):
            auth_failure = result
        if isinstance(result, (ConfigEntryNotReady, ConfigEntryAuthFailed)):
            failures.append(result)
        elif isinstance(result, BaseException):
            raise result
    if failures and len(failures) == len(results):
        raise auth_failure or failures[0]
    for coordinator, result in zip(coordinators.values(), results, strict=True):
        if isinstance(result, (ConfigEntryNotReady, ConfigEntryAuthFailed)):
            _LOGGER.error(
                "Error fetching initial data for %s: %s",
                coordinator.device.name,
                result,
            )
    if auth_failure:
        entry.async_start_reauth(hass)

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: MitsubishiComfortCloudConfigEntry
) -> None:
    """Unload Mitsubishi Comfort Cloud."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
