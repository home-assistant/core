"""The Sunsynk integration."""

import asyncio

from sunsynk.client import SunsynkClient
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import SunsynkConfigEntry, SunsynkDataUpdateCoordinator
from .entity import inverter_device_info

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SunsynkConfigEntry) -> bool:
    """Set up Sunsynk from a config entry."""
    client = SunsynkClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    try:
        inverters = await client.get_inverters()
    except SunsynkAuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
    except SunsynkConnectionError as err:
        raise ConfigEntryNotReady(err) from err

    coordinators = [
        SunsynkDataUpdateCoordinator(hass, entry, client, inverter)
        for inverter in inverters
    ]
    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        )
    )
    entry.runtime_data = coordinators

    # The battery device links to its inverter, so the inverter must exist first.
    device_registry = dr.async_get(hass)
    for inverter in inverters:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **inverter_device_info(inverter)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SunsynkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
