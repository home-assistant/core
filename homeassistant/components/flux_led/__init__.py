"""The Flux LED/MagicLight integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final

from flux_led import BulbScanner, WifiLedBulb

from homeassistant import config_entries
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MODE,
    CONF_DEVICES,
    CONF_HOST,
    CONF_MAC,
    CONF_MODE,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COLORS,
    CONF_CUSTOM_EFFECT,
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    CONF_SPEED_PCT,
    CONF_TRANSITION,
    DEFAULT_EFFECT_SPEED,
    DISCOVER_SCAN_TIMEOUT,
    DOMAIN,
    FLUX_HOST,
    FLUX_LED_EXCEPTIONS,
    FLUX_MAC,
    MODE_AUTO,
    STARTUP_SCAN_TIMEOUT,
    TRANSITION_GRADUAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final = ["light"]
DISCOVERY_INTERVAL: Final = timedelta(minutes=15)
REQUEST_REFRESH_DELAY: Final = 0.35


async def async_wifi_bulb_for_host(hass: HomeAssistant, host: str) -> WifiLedBulb:
    """Create a WifiLedBulb from a host."""
    return await hass.async_add_executor_job(WifiLedBulb, host)


async def async_discover_devices(
    hass: HomeAssistant, timeout: int
) -> list[dict[str, str]]:
    """Discover ledned devices."""

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


@callback
def async_import_from_yaml(
    hass: HomeAssistant,
    config: ConfigType,
    discovered_mac_by_host: dict[str, str],
) -> None:
    """Import devices from yaml."""
    for entry_config in config.get(LIGHT_DOMAIN, []):
        if entry_config.get(CONF_PLATFORM) != DOMAIN:
            continue
        for host, device_config in entry_config[CONF_DEVICES].items():
            _LOGGER.warning(
                "Configuring flux_led via yaml is deprecated; the configuration for"
                " %s has been migrated to a config entry and can be safely removed",
                host,
            )
            custom_effects = device_config.get(CONF_CUSTOM_EFFECT, {})
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={
                        CONF_HOST: host,
                        CONF_MAC: discovered_mac_by_host.get(host),
                        CONF_NAME: device_config[CONF_NAME],
                        CONF_PROTOCOL: device_config.get(CONF_PROTOCOL),
                        CONF_MODE: device_config.get(ATTR_MODE, MODE_AUTO),
                        CONF_CUSTOM_EFFECT_COLORS: str(custom_effects.get(CONF_COLORS)),
                        CONF_CUSTOM_EFFECT_SPEED_PCT: custom_effects.get(
                            CONF_SPEED_PCT, DEFAULT_EFFECT_SPEED
                        ),
                        CONF_CUSTOM_EFFECT_TRANSITION: custom_effects.get(
                            CONF_TRANSITION, TRANSITION_GRADUAL
                        ),
                    },
                )
            )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the flux_led component."""
    hass.data[DOMAIN] = {}
    discovered_devices = await async_discover_devices(hass, STARTUP_SCAN_TIMEOUT)
    discovered_mac_by_host = {
        device[FLUX_HOST]: device[FLUX_MAC] for device in discovered_devices
    }

    async_import_from_yaml(hass, config, discovered_mac_by_host)

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT)
        )

    async_trigger_discovery(hass, discovered_devices)
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
