"""The Nature Remo integration."""

from aionatureremo import NatureRemoClient

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import NatureRemoConfigEntry, NatureRemoCoordinator
from .entity import build_appliance_device_info, build_remo_device_info

PLATFORMS: list[Platform] = [Platform.SENSOR]


@callback
def _async_register_devices(hass: HomeAssistant, entry: NatureRemoConfigEntry) -> None:
    """Register every Remo hub and every appliance up front.

    Appliance entities link to their hub via ``via_device``, but an
    energy-only hub (Remo E / E lite) reports no sensor events, so its
    device would never be registered by an entity and its appliances would
    dangle. Appliances are re-registered from the same builder on every
    poll so a nickname edited in the Nature app reaches the device
    registry. Hubs come first so no ``via_device`` target is missing.
    """
    coordinator = entry.runtime_data
    device_registry = dr.async_get(hass)
    for device in coordinator.data.devices.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **build_remo_device_info(device),
        )
    for appliance in coordinator.data.appliances.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **build_appliance_device_info(appliance),
        )


async def async_setup_entry(hass: HomeAssistant, entry: NatureRemoConfigEntry) -> bool:
    """Set up Nature Remo from a config entry."""
    client = NatureRemoClient(entry.data[CONF_API_TOKEN], async_get_clientsession(hass))
    coordinator = NatureRemoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _async_register_devices(hass, entry)
    entry.async_on_unload(
        coordinator.async_add_listener(lambda: _async_register_devices(hass, entry))
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NatureRemoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
