"""The Kohler Energy Management (KEM) integration."""

from __future__ import annotations

import logging

from aiokem import AuthenticationError

from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONNECTION_EXCEPTIONS,
    DEVICE_DATA_DEVICES,
    DEVICE_DATA_DISPLAY_NAME,
    DEVICE_DATA_ID,
    DOMAIN,
)
from .coordinator import KemUpdateCoordinator
from .data import HAAioKem
from .types import KemConfigEntry, KemRuntimeData

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: KemConfigEntry) -> bool:
    """Set up KEM from a config entry."""
    websession = async_get_clientsession(hass)
    kem = HAAioKem(session=websession, hass=hass, config_entry=entry)
    kem.set_retry_policy(retry_count=3, retry_delays=[5, 10, 20])
    try:
        await kem.login()
    except AuthenticationError as ex:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
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
    if hasattr(entry, "runtime_data") and hasattr(entry.runtime_data, "kem"):
        await entry.runtime_data.kem.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
