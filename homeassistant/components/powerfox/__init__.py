"""The Powerfox integration."""

import asyncio

from powerfox import (
    DeviceType,
    Powerfox,
    PowerfoxAuthenticationError,
    PowerfoxConnectionError,
)

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import (
    PowerfoxAuthState,
    PowerfoxConfigEntry,
    PowerfoxDataUpdateCoordinator,
    PowerfoxReportDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _get_auth_state(
    hass: HomeAssistant, entry: PowerfoxConfigEntry
) -> PowerfoxAuthState:
    """Keep authentication investigation state across setup retries."""
    # Preserve authentication state across failed setup attempts.
    # pylint: disable-next=home-assistant-use-runtime-data
    states: dict[str, PowerfoxAuthState] = hass.data.setdefault(DOMAIN, {})
    return states.setdefault(entry.entry_id, PowerfoxAuthState())


def reset_auth_state(hass: HomeAssistant, entry_id: str) -> None:
    """Reset authentication investigation after credentials are validated."""
    # Preserve authentication state across failed setup attempts.
    # pylint: disable-next=home-assistant-use-runtime-data
    states: dict[str, PowerfoxAuthState] = hass.data.get(DOMAIN, {})
    if state := states.get(entry_id):
        state.record_success()


async def async_setup_entry(hass: HomeAssistant, entry: PowerfoxConfigEntry) -> bool:
    """Set up Powerfox from a config entry."""
    client = Powerfox(
        username=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    auth_state = _get_auth_state(hass, entry)

    try:
        devices = await client.all_devices()
    except PowerfoxAuthenticationError as err:
        await client.close()
        if auth_state.record_failure(dt_util.utcnow()):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from err
    except PowerfoxConnectionError as err:
        await client.close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err

    auth_state.record_success()

    coordinators: list[
        PowerfoxDataUpdateCoordinator | PowerfoxReportDataUpdateCoordinator
    ] = []
    for device in devices:
        if device.type == DeviceType.GAS_METER:
            coordinators.append(
                PowerfoxReportDataUpdateCoordinator(
                    hass, entry, client, device, auth_state
                )
            )
            continue
        coordinators.append(
            PowerfoxDataUpdateCoordinator(hass, entry, client, device, auth_state)
        )

    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PowerfoxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PowerfoxConfigEntry) -> None:
    """Remove the shared authentication state when an entry is deleted."""
    # Preserve authentication state across failed setup attempts.
    # pylint: disable-next=home-assistant-use-runtime-data
    states: dict[str, PowerfoxAuthState] = hass.data.get(DOMAIN, {})
    states.pop(entry.entry_id, None)
