"""The Lunatone integration."""

from typing import Final

from lunatone_rest_api_client import Auth, Devices, Info

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import (
    LunatoneConfigEntry,
    LunatoneData,
    LunatoneDevicesDataUpdateCoordinator,
    LunatoneInfoDataUpdateCoordinator,
)

PLATFORMS: Final[list[Platform]] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: LunatoneConfigEntry) -> bool:
    """Set up Lunatone from a config entry."""
    auth = Auth(async_get_clientsession(hass), entry.data[CONF_URL])
    info_api = Info(auth)
    devices_api = Devices(auth)

    coordinator_info = LunatoneInfoDataUpdateCoordinator(hass, entry, info_api)
    await coordinator_info.async_config_entry_first_refresh()

    if info_api.serial_number is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="missing_device_info"
        )

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(info_api.serial_number))},
        name=info_api.name,
        manufacturer="Lunatone",
        sw_version=info_api.version,
        hw_version=info_api.data.device.pcb,
        configuration_url=entry.data[CONF_URL],
        serial_number=info_api.serial_number,
        model_id=(
            f"{info_api.data.device.article_number}{info_api.data.device.article_info}"
        ),
    )

    coordinator_devices = LunatoneDevicesDataUpdateCoordinator(hass, entry, devices_api)
    await coordinator_devices.async_config_entry_first_refresh()

    entry.runtime_data = LunatoneData(coordinator_info, coordinator_devices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LunatoneConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
