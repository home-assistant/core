"""The swidget integration."""

from datetime import timedelta
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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SwidgetDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.LIGHT]
DISCOVERY_INTERVAL = timedelta(minutes=15)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


SwidgetConfigEntry = ConfigEntry[SwidgetDataUpdateCoordinator]


async def async_discover_devices(
    hass: HomeAssistant,
) -> dict[str, SwidgetDiscoveredDevice]:
    """Force discover Swidget devices using SSDP."""
    devices: dict[str, SwidgetDiscoveredDevice]
    devices = await discover_devices(timeout=15)  # type: ignore [no-untyped-call]
    return devices


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Swidget component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SwidgetConfigEntry) -> bool:
    """Set up swidget from a config entry."""

    # Discover the device using provided host and password
    device = await discover_single(
        host=entry.data[CONF_HOST],
        token_name="x-secret-key",
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
        LOGGER.error("Unsupported device type discovered: %s", {type(device).__name__})
        return False

    # Create the coordinator for managing updates
    coordinator = SwidgetDataUpdateCoordinator(hass, device, config_entry=entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Forward the entry setup to other platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start the device and create a background task for websocket listening
    await device.start()

    # # Start listening
    if device.get_websocket() is not None:
        entry.async_create_background_task(
            hass,
            device.get_websocket().listen(),  # type: ignore[union-attr]
            "websocket_connection",
        )

    # Perform additional asynchronous initialization, return True if successful
    if await coordinator.async_initialize():
        entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
        return True

    return False


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SwidgetConfigEntry) -> bool:
    """Unload a config entry."""
    device: SwidgetDevice = entry.runtime_data.device
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await device.stop()
    return unload_ok
