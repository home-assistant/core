"""The swidget integration."""

import logging

from swidget import (
    SwidgetDevice,
    SwidgetDimmer,
    SwidgetOutlet,
    SwidgetSwitch,
    SwidgetTimerSwitch,
)
from swidget.discovery import SwidgetDiscoveredDevice, discover_devices, discover_single

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import TOKEN_NAME
from .coordinator import SwidgetDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.LIGHT]


SwidgetConfigEntry = ConfigEntry[SwidgetDataUpdateCoordinator]


async def async_discover_devices(
    hass: HomeAssistant,
) -> dict[str, SwidgetDiscoveredDevice]:
    """Force discover Swidget devices using SSDP."""
    devices: dict[str, SwidgetDiscoveredDevice]
    devices = await discover_devices(timeout=15)  # type: ignore [no-untyped-call]
    return devices


async def async_setup_entry(hass: HomeAssistant, entry: SwidgetConfigEntry) -> bool:
    """Set up swidget from a config entry."""

    # Discover the device using provided host and password
    device = await discover_single(
        host=entry.data[CONF_HOST],
        token_name=TOKEN_NAME,
        password=entry.data[CONF_PASSWORD],
        use_https=True,
        use_websockets=True,
    )

    # Define the expected device types
    valid_device_types = (
        SwidgetDimmer,
        SwidgetOutlet,
        SwidgetSwitch,
        SwidgetTimerSwitch,
    )

    # Check if the discovered device is of an expected type
    if not isinstance(device, valid_device_types):
        raise ConfigEntryError(
            f"Unsupported device type discovered: {type(device).__name__}"
        )

    # Start the device and create a background task for websocket listening
    await device.start()
    entry.async_create_background_task(
        hass,
        device.get_websocket().run(),  # type: ignore[union-attr]
        "websocket_connection",
    )

    coordinator = SwidgetDataUpdateCoordinator(hass, device, config_entry=entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await coordinator.async_initialize()
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SwidgetConfigEntry) -> bool:
    """Unload a config entry."""
    device: SwidgetDevice = entry.runtime_data.device
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await device.stop()
    return unload_ok
