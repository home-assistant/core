"""The Zinvolt integration."""

import asyncio

from zinvolt import ZinvoltClient
from zinvolt.exceptions import ZinvoltAuthenticationError, ZinvoltError

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import ZinvoltConfigEntry, ZinvoltDeviceCoordinator

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ZinvoltConfigEntry) -> None:
    """Set up Zinvolt from a config entry."""
    session = async_get_clientsession(hass)
    client = ZinvoltClient(entry.data[CONF_ACCESS_TOKEN], session=session)

    try:
        batteries = await client.get_batteries()
    except ZinvoltAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err
    except ZinvoltError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="update_failed"
        ) from err

    coordinators: dict[str, ZinvoltDeviceCoordinator] = {}
    tasks = []
    for battery in batteries:
        coordinator = ZinvoltDeviceCoordinator(hass, entry, client, battery)
        tasks.append(coordinator.async_config_entry_first_refresh())
        coordinators[battery.identifier] = coordinator
    await asyncio.gather(*tasks)

    entry.runtime_data = coordinators

    # Register the main battery devices before forwarding platforms so unit
    # sub-devices can resolve their via_device_id parent.
    device_registry = dr.async_get(hass)
    for coordinator in coordinators.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, coordinator.data.battery.serial_number)},
        )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ZinvoltConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
