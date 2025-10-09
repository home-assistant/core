"""The LetPot integration."""

from __future__ import annotations

import asyncio

from letpot.client import LetPotClient
from letpot.converters import CONVERTERS
from letpot.deviceclient import LetPotDeviceClient
from letpot.exceptions import LetPotAuthenticationException, LetPotException
from letpot.models import AuthenticationInfo

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCESS_TOKEN_EXPIRES,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES,
    CONF_USER_ID,
)
from .coordinator import LetPotConfigEntry, LetPotDeviceCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup_entry(hass: HomeAssistant, entry: LetPotConfigEntry) -> bool:
    """Set up LetPot from a config entry."""

    auth = AuthenticationInfo(
        access_token=entry.data[CONF_ACCESS_TOKEN],
        access_token_expires=entry.data[CONF_ACCESS_TOKEN_EXPIRES],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        refresh_token_expires=entry.data[CONF_REFRESH_TOKEN_EXPIRES],
        user_id=entry.data[CONF_USER_ID],
        email=entry.data[CONF_EMAIL],
    )
    websession = async_get_clientsession(hass)
    client = LetPotClient(websession, auth)

    if not auth.is_valid:
        try:
            auth = await client.refresh_token()
            hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_ACCESS_TOKEN: auth.access_token,
                    CONF_ACCESS_TOKEN_EXPIRES: auth.access_token_expires,
                    CONF_REFRESH_TOKEN: auth.refresh_token,
                    CONF_REFRESH_TOKEN_EXPIRES: auth.refresh_token_expires,
                    CONF_USER_ID: auth.user_id,
                    CONF_EMAIL: auth.email,
                },
            )
        except LetPotAuthenticationException as exc:
            raise ConfigEntryAuthFailed from exc

    try:
        devices = await client.get_devices()
    except LetPotAuthenticationException as exc:
        raise ConfigEntryAuthFailed from exc
    except LetPotException as exc:
        raise ConfigEntryNotReady from exc

    device_client = LetPotDeviceClient(auth)

    coordinators: list[LetPotDeviceCoordinator] = [
        LetPotDeviceCoordinator(hass, entry, device, device_client)
        for device in devices
        if any(converter.supports_type(device.device_type) for converter in CONVERTERS)
    ]

    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LetPotConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        for coordinator in entry.runtime_data:
            await coordinator.device_client.unsubscribe(
                coordinator.device.serial_number
            )
    return unload_ok
