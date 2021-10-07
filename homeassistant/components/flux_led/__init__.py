"""The Flux LED/MagicLight integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final

from flux_led import BulbScanner, WifiLedBulb

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DISCOVER_SCAN_TIMEOUT,
    DOMAIN,
    FLUX_LED_DISCOVERY,
    FLUX_LED_EXCEPTIONS,
    STARTUP_SCAN_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final = ["light"]
DISCOVERY_INTERVAL: Final = timedelta(minutes=15)
REQUEST_REFRESH_DELAY: Final = 0.65


async def async_wifi_bulb_for_host(hass: HomeAssistant, host: str) -> WifiLedBulb:
    """Create a WifiLedBulb from a host."""
    return await hass.async_add_executor_job(WifiLedBulb, host)


async def async_discover_devices(
    hass: HomeAssistant, timeout: int
) -> list[dict[str, str]]:
    """Discover flux led devices."""

    def _scan_with_timeout() -> list[dict[str, str]]:
        scanner = BulbScanner()
        discovered: list[dict[str, str]] = scanner.scan(timeout=timeout)
        return discovered

    return await hass.async_add_executor_job(_scan_with_timeout)


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[dict[str, Any]],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_DISCOVERY},
                data=device,
            )
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the flux_led component."""
    domain_data = hass.data[DOMAIN] = {}
    domain_data[FLUX_LED_DISCOVERY] = await async_discover_devices(
        hass, STARTUP_SCAN_TIMEOUT
    )

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT)
        )

    async_trigger_discovery(hass, domain_data[FLUX_LED_DISCOVERY])
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_discovery)
    async_track_time_interval(hass, _async_discovery, DISCOVERY_INTERVAL)
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flux LED/MagicLight from a config entry."""

    coordinator = FluxLedUpdateCoordinator(hass, entry.data[CONF_HOST])
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class FluxLedUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific flux_led device."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific device."""
        self.host = host
        self.device: WifiLedBulb | None = None
        update_interval = timedelta(seconds=5)
        super().__init__(
            hass,
            _LOGGER,
            name=host,
            update_interval=update_interval,
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        try:
            if not self.device:
                self.device = await async_wifi_bulb_for_host(self.hass, self.host)
            else:
                await self.hass.async_add_executor_job(self.device.update_state)
        except FLUX_LED_EXCEPTIONS as ex:
            raise UpdateFailed(ex) from ex

        if not self.device.raw_state:
            raise UpdateFailed("The device failed to update")
