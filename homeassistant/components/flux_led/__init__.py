"""The Flux LED/MagicLight integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final, cast

from flux_led import DeviceType
from flux_led.aio import AIOWifiLedBulb
from flux_led.const import ATTR_ID

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DISCOVER_SCAN_TIMEOUT,
    DOMAIN,
    FLUX_LED_DISCOVERY,
    FLUX_LED_EXCEPTIONS,
    SIGNAL_STATE_UPDATED,
    STARTUP_SCAN_TIMEOUT,
)
from .discovery import (
    async_clear_discovery_cache,
    async_discover_device,
    async_discover_devices,
    async_get_discovery,
    async_trigger_discovery,
    async_update_entry_from_discovery,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BY_TYPE: Final = {
    DeviceType.Bulb: [Platform.LIGHT, Platform.NUMBER, Platform.SWITCH],
    DeviceType.Switch: [Platform.SWITCH],
}
DISCOVERY_INTERVAL: Final = timedelta(minutes=15)
REQUEST_REFRESH_DELAY: Final = 1.5


@callback
def async_wifi_bulb_for_host(host: str) -> AIOWifiLedBulb:
    """Create a AIOWifiLedBulb from a host."""
    return AIOWifiLedBulb(host)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the flux_led component."""
    domain_data = hass.data.setdefault(DOMAIN, {})
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flux LED/MagicLight from a config entry."""
    host = entry.data[CONF_HOST]
    device: AIOWifiLedBulb = async_wifi_bulb_for_host(host)
    signal = SIGNAL_STATE_UPDATED.format(device.ipaddr)

    @callback
    def _async_state_changed(*_: Any) -> None:
        _LOGGER.debug("%s: Device state updated: %s", device.ipaddr, device.raw_state)
        async_dispatcher_send(hass, signal)

    try:
        await device.async_setup(_async_state_changed)
    except FLUX_LED_EXCEPTIONS as ex:
        raise ConfigEntryNotReady(
            str(ex) or f"Timed out trying to connect to {device.ipaddr}"
        ) from ex

    # UDP probe after successful connect only
    directed_discovery = None
    if discovery := async_get_discovery(hass, host):
        directed_discovery = False
    elif discovery := await async_discover_device(hass, host):
        directed_discovery = True

    if discovery:
        if entry.unique_id:
            assert discovery[ATTR_ID] is not None
            mac = dr.format_mac(cast(str, discovery[ATTR_ID]))
            if mac != entry.unique_id:
                # The device is offline and another flux_led device is now using the ip address
                raise ConfigEntryNotReady(
                    f"Unexpected device found at {host}; Expected {entry.unique_id}, found {mac}"
                )
        if directed_discovery:
            # Only update the entry once we have verified the unique id
            # is either missing or we have verified it matches
            async_update_entry_from_discovery(hass, entry, discovery)
        device.discovery = discovery

    coordinator = FluxLedUpdateCoordinator(hass, device, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    platforms = PLATFORMS_BY_TYPE[device.device_type]
    hass.config_entries.async_setup_platforms(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device: AIOWifiLedBulb = hass.data[DOMAIN][entry.entry_id].device
    platforms = PLATFORMS_BY_TYPE[device.device_type]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        # Make sure we probe the device again in case something has changed externally
        async_clear_discovery_cache(hass, entry.data[CONF_HOST])
        del hass.data[DOMAIN][entry.entry_id]
        await device.async_stop()
    return unload_ok


class FluxLedUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific flux_led device."""

    def __init__(
        self, hass: HomeAssistant, device: AIOWifiLedBulb, entry: ConfigEntry
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific device."""
        self.device = device
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=self.device.ipaddr,
            update_interval=timedelta(seconds=10),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        try:
            await self.device.async_update()
        except FLUX_LED_EXCEPTIONS as ex:
            raise UpdateFailed(ex) from ex
