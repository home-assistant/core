"""The Home Assistant Yellow integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout

from homeassistant.components.hassio import (
    HassioAPIError,
    async_get_yellow_settings,
    get_os_info,
)
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    check_multi_pan_addon,
    get_zigbee_socket,
    multi_pan_addon_using_device,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, RADIO_DEVICE, ZHA_HW_DISCOVERY_DATA
from .models import YellowData

PLATFORMS = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant Yellow config entry."""
    if (os_info := get_os_info(hass)) is None:
        # The hassio integration has not yet fetched data from the supervisor
        raise ConfigEntryNotReady

    board: str | None
    if (board := os_info.get("board")) is None or board != "yellow":
        # Not running on a Home Assistant Yellow, Home Assistant may have been migrated
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    try:
        await check_multi_pan_addon(hass)
    except HomeAssistantError as err:
        raise ConfigEntryNotReady from err

    async def async_update_data() -> dict[str, bool]:
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                led_settings: dict[str, bool] = await async_get_yellow_settings(hass)
                return led_settings
        except HassioAPIError as err:
            raise UpdateFailed(
                "Failed to call supervisor endpoint /os/boards/yellow"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=DOMAIN,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30),
    )
    await coordinator.async_config_entry_first_refresh()

    if not await multi_pan_addon_using_device(hass, RADIO_DEVICE):
        hw_discovery_data = ZHA_HW_DISCOVERY_DATA
    else:
        hw_discovery_data = {
            "name": "Yellow Multi-PAN",
            "port": {
                "path": get_zigbee_socket(),
            },
            "radio_type": "ezsp",
        }

    await hass.config_entries.flow.async_init(
        "zha",
        context={"source": "hardware"},
        data=hw_discovery_data,
    )

    hass.data[DOMAIN] = YellowData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.pop(DOMAIN)
    return unload_ok
