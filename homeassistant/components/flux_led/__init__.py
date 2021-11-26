"""The Flux LED/MagicLight integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final, cast

from flux_led import DeviceType
from flux_led.aio import AIOWifiLedBulb
from flux_led.aioscanner import AIOBulbScanner
from flux_led.const import ATTR_ID, ATTR_IPADDR, ATTR_MODEL, ATTR_MODEL_DESCRIPTION

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, EVENT_HOMEASSISTANT_STARTED
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

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BY_TYPE: Final = {
    DeviceType.Bulb: ["light", "number"],
    DeviceType.Switch: ["switch"],
}
DISCOVERY_INTERVAL: Final = timedelta(minutes=15)
REQUEST_REFRESH_DELAY: Final = 1.5


@callback
def async_wifi_bulb_for_host(host: str) -> AIOWifiLedBulb:
    """Create a AIOWifiLedBulb from a host."""
    return AIOWifiLedBulb(host)


@callback
def async_name_from_discovery(device: dict[str, Any]) -> str:
    """Convert a flux_led discovery to a human readable name."""
    if (mac := device.get(ATTR_ID)) is None:
        return cast(str, device[ATTR_IPADDR])
    short_mac = mac[-6:]
    if device.get(ATTR_MODEL_DESCRIPTION):
        return f"{device[ATTR_MODEL_DESCRIPTION]} {short_mac}"
    return f"{device[ATTR_MODEL]} {short_mac}"


@callback
def async_update_entry_from_discovery(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, device: dict[str, Any]
) -> None:
    """Update a config entry from a flux_led discovery."""
    name = async_name_from_discovery(device)
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_NAME: name},
        title=name,
        unique_id=dr.format_mac(device[ATTR_ID]),
    )


async def async_discover_devices(
    hass: HomeAssistant, timeout: int, address: str | None = None
) -> list[dict[str, str]]:
    """Discover flux led devices."""
    scanner = AIOBulbScanner()
    try:
        discovered: list[dict[str, str]] = await scanner.async_scan(
            timeout=timeout, address=address
        )
    except OSError as ex:
        _LOGGER.debug("Scanning failed with error: %s", ex)
        return []
    else:
        return discovered


async def async_discover_device(
    hass: HomeAssistant, host: str
) -> dict[str, str] | None:
    """Direct discovery at a single ip instead of broadcast."""
    # If we are missing the unique_id we should be able to fetch it
    # from the device by doing a directed discovery at the host only
    for device in await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT, host):
        if device[ATTR_IPADDR] == host:
            return device
    return None


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
    host = entry.data[CONF_HOST]
    if not entry.unique_id:
        if discovery := await async_discover_device(hass, host):
            async_update_entry_from_discovery(hass, entry, discovery)

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
    coordinator = FluxLedUpdateCoordinator(hass, device)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(
        entry, PLATFORMS_BY_TYPE[device.device_type]
    )
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device: AIOWifiLedBulb = hass.data[DOMAIN][entry.entry_id].device
    platforms = PLATFORMS_BY_TYPE[device.device_type]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.device.async_stop()
    return unload_ok


class FluxLedUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific flux_led device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: AIOWifiLedBulb,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific device."""
        self.device = device
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
