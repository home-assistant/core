"""The Nature Remo integration."""

from aionatureremo import APPLIANCE_TYPE_SMART_METER, NatureRemoClient

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import NatureRemoConfigEntry, NatureRemoCoordinator
from .entity import build_appliance_device_info, build_remo_device_info

PLATFORMS: list[Platform] = [Platform.SENSOR]


@callback
def _async_register_devices(hass: HomeAssistant, entry: NatureRemoConfigEntry) -> None:
    """Register the Remo hubs and the appliances this platform exposes.

    Registration is eager because an energy-only hub (Remo E / E lite)
    has no entities to create its device, and repeats on every poll so
    renames in the Nature app reach the device registry.
    """
    coordinator = entry.runtime_data
    device_registry = dr.async_get(hass)
    hub_ids: dict[str, str] = {}
    for device in coordinator.data.devices.values():
        device_entry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **build_remo_device_info(device),
        )
        hub_ids[device.id] = device_entry.id
    for appliance in coordinator.data.appliances.values():
        if (
            appliance.type != APPLIANCE_TYPE_SMART_METER
            or appliance.smart_meter is None
        ):
            continue
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **build_appliance_device_info(
                appliance, hub_ids.get(appliance.device_id or "")
            ),
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
