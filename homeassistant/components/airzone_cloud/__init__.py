"""The Airzone Cloud integration."""

from aioairzone_cloud.cloudapi import AirzoneCloudApi
from aioairzone_cloud.common import ConnectionOptions
from aioairzone_cloud.const import (
    AZD_FIRMWARE,
    AZD_MODEL,
    AZD_NAME,
    AZD_SYSTEMS,
    AZD_WEBSERVER,
    AZD_WEBSERVERS,
)

from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneCloudConfigEntry, AirzoneUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: AirzoneCloudConfigEntry
) -> bool:
    """Set up Airzone Cloud from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        True,
    )

    airzone = AirzoneCloudApi(aiohttp_client.async_get_clientsession(hass), options)
    await airzone.login()
    inst_list = await airzone.list_installations()
    for inst in inst_list:
        if inst.get_id() == entry.data[CONF_ID]:
            airzone.select_installation(inst)
            await airzone.update_installation(inst)

    coordinator = AirzoneUpdateCoordinator(hass, entry, airzone)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    _async_register_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


@callback
def _async_register_devices(
    hass: HomeAssistant,
    entry: AirzoneCloudConfigEntry,
    coordinator: AirzoneUpdateCoordinator,
) -> None:
    """Register WebServer and System devices referenced as via_device parents.

    Child devices resolve their via_device_id at add time, so the parents must
    already exist regardless of which platform creates their own entities.
    """
    device_registry = dr.async_get(hass)

    for ws_id, ws_data in coordinator.data.get(AZD_WEBSERVERS, {}).items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, ws_id)},
            identifiers={(DOMAIN, ws_id)},
            manufacturer=MANUFACTURER,
            model="WebServer",
            name=ws_data[AZD_NAME],
            sw_version=ws_data[AZD_FIRMWARE],
        )

    for system_id, system_data in coordinator.data.get(AZD_SYSTEMS, {}).items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, system_id)},
            manufacturer=MANUFACTURER,
            model=system_data.get(AZD_MODEL),
            name=system_data[AZD_NAME],
            sw_version=system_data.get(AZD_FIRMWARE),
            via_device_id=dr.async_get_device_id_by_identifier(
                hass,
                (DOMAIN, system_data[AZD_WEBSERVER]),
                config_entry_id=entry.entry_id,
            ),
        )


async def async_unload_entry(
    hass: HomeAssistant, entry: AirzoneCloudConfigEntry
) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.airzone.logout()

    return unload_ok
