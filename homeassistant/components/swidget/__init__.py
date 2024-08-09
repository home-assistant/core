"""The swidget integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from swidget.discovery import SwidgetDiscoveredDevice, discover_devices, discover_single
from swidget.swidgetdevice import SwidgetDevice

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SwidgetDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.LIGHT]
DISCOVERY_INTERVAL = timedelta(minutes=15)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class SwidgetData:
    """Store runtime data."""

    coordinator: SwidgetDataUpdateCoordinator


SwidgetConfigEntry = ConfigEntry[SwidgetData]


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: dict[str, SwidgetDiscoveredDevice],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices.values():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data={
                    CONF_NAME: device.friendly_name,
                    CONF_HOST: device.host,
                    CONF_MAC: device.mac,
                },
            )
        )


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
    if discovered_devices := await async_discover_devices(hass):
        async_trigger_discovery(hass, discovered_devices)

    async def _async_discovery(*_: Any) -> None:
        if discovered := await async_discover_devices(hass):
            async_trigger_discovery(hass, discovered)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_discovery)
    async_track_time_interval(hass, _async_discovery, DISCOVERY_INTERVAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up swidget from a config entry."""

    device = await discover_single(
        host=entry.data[CONF_HOST],
        token_name="x-secret-key",
        password=entry.data[CONF_PASSWORD],
        use_https=True,
        use_websockets=True,
    )
    coordinator = SwidgetDataUpdateCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = SwidgetData(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    try:
        await device.start()
        hass.async_create_background_task(
            device.get_websocket().listen(), "websocket_connection"
        )
    except Exception as ex:
        raise ConfigEntryNotReady(
            f"Unable to connect to Swidget device over websockets: {entry.data[CONF_HOST]}"
        ) from ex
    if await coordinator.async_initialize():
        return True
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = entry.runtime_data
    device: SwidgetDevice = data.coordinator.device
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await device.stop()
    return unload_ok
