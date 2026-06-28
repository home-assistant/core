"""SMLIGHT SLZB device integration."""

from pysmlight import Api2

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .bluetooth import async_connect_scanner
from .const import DOMAIN
from .coordinator import (
    SmConfigEntry,
    SmDataUpdateCoordinator,
    SmFirmwareUpdateCoordinator,
    SmlightData,
    device_info,
)
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.INFRARED,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SMLIGHT services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SmConfigEntry) -> bool:
    """Set up SMLIGHT from a config entry."""
    client = Api2(host=entry.data[CONF_HOST], session=async_get_clientsession(hass))

    data_coordinator = SmDataUpdateCoordinator(hass, entry, client)
    firmware_coordinator = SmFirmwareUpdateCoordinator(hass, entry, client)

    await data_coordinator.async_config_entry_first_refresh()
    await firmware_coordinator.async_config_entry_first_refresh()

    info = data_coordinator.data.info

    unique_id = data_coordinator.unique_id
    assert unique_id is not None

    if info.legacy_api < 2:
        entry.async_create_background_task(
            hass, client.sse.client(), "smlight-sse-client"
        )

    if info.ble is not None and info.ble.proxy_enabled:
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **device_info(info, client.host),
        )
        data_coordinator.device_id = device.id
        entry.async_on_unload(
            async_connect_scanner(hass, entry, info.model, data_coordinator.device_id)
        )

    entry.runtime_data = SmlightData(
        data=data_coordinator,
        firmware=firmware_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmConfigEntry) -> bool:
    """Unload SMLIGHT config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
