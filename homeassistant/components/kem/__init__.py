"""The Kohler Energy Management (KEM) integration."""

from __future__ import annotations

import logging

from aiokem import AioKem, AuthenticationError

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_REFRESH_TOKEN,
    CONNECTION_EXCEPTIONS,
    DEVICE_DATA_DEVICES,
    DEVICE_DATA_DISPLAY_NAME,
    DEVICE_DATA_ID,
    DOMAIN,
)
from .coordinator import KemConfigEntry, KemRuntimeData, KemUpdateCoordinator

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: KemConfigEntry) -> bool:
    """Set up KEM from a config entry."""
    websession = async_get_clientsession(hass)
    kem = AioKem(session=websession)

    async def async_refresh_token_update(refresh_token: str) -> None:
        """Handle refresh token update."""
        _LOGGER.debug("Saving refresh token")
        # Update the config entry with the new refresh token
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_REFRESH_TOKEN: refresh_token},
        )

    kem.set_refresh_token_callback(async_refresh_token_update)
    kem.set_retry_policy(retry_count=3, retry_delays=[5, 10, 20])

    try:
        await kem.authenticate(
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
            entry.data.get(CONF_REFRESH_TOKEN),
        )
    except AuthenticationError as ex:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={CONF_EMAIL: entry.data[CONF_EMAIL]},
        ) from ex
    except CONNECTION_EXCEPTIONS as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from ex
    coordinators: dict[int, KemUpdateCoordinator] = {}
    homes = await kem.get_homes()

    entry.runtime_data = KemRuntimeData(
        coordinators=coordinators,
        kem=kem,
        homes=homes,
    )

    for home_data in homes:
        for device_data in home_data[DEVICE_DATA_DEVICES]:
            device_id = device_data[DEVICE_DATA_ID]
            coordinator = KemUpdateCoordinator(
                hass=hass,
                logger=_LOGGER,
                config_entry=entry,
                home_data=home_data,
                device_id=device_id,
                device_data=device_data,
                kem=kem,
                name=f"{DOMAIN} {device_data[DEVICE_DATA_DISPLAY_NAME]}",
            )
            # Intentionally done in series to avoid overloading
            # the KEM API with requests
            await coordinator.async_config_entry_first_refresh()
            coordinators[device_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KemConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.kem.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
