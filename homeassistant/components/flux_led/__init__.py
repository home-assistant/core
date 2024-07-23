"""The Flux LED/MagicLight integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final, cast

from flux_led import DeviceType
from flux_led.aio import AIOWifiLedBulb
from flux_led.const import ATTR_ID, WhiteChannelType
from flux_led.scanner import FluxLEDDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_WHITE_CHANNEL_TYPE,
    DISCOVER_SCAN_TIMEOUT,
    DOMAIN,
    FLUX_LED_DISCOVERY,
    FLUX_LED_DISCOVERY_SIGNAL,
    FLUX_LED_EXCEPTIONS,
    SIGNAL_STATE_UPDATED,
)
from .coordinator import FluxLedUpdateCoordinator
from .discovery import (
    async_build_cached_discovery,
    async_clear_discovery_cache,
    async_discover_device,
    async_discover_devices,
    async_get_discovery,
    async_trigger_discovery,
    async_update_entry_from_discovery,
)
from .util import mac_matches_by_one

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BY_TYPE: Final = {
    DeviceType.Bulb: [
        Platform.BUTTON,
        Platform.LIGHT,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    DeviceType.Switch: [
        Platform.BUTTON,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
}
DISCOVERY_INTERVAL: Final = timedelta(minutes=15)
REQUEST_REFRESH_DELAY: Final = 1.5
NAME_TO_WHITE_CHANNEL_TYPE: Final = {
    option.name.lower(): option for option in WhiteChannelType
}

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@callback
def async_wifi_bulb_for_host(
    host: str, discovery: FluxLEDDiscovery | None
) -> AIOWifiLedBulb:
    """Create a AIOWifiLedBulb from a host."""
    return AIOWifiLedBulb(host, discovery=discovery)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the flux_led component."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[FLUX_LED_DISCOVERY] = []

    @callback
    def _async_start_background_discovery(*_: Any) -> None:
        """Run discovery in the background."""
        hass.async_create_background_task(
            _async_discovery(), "flux_led-discovery", eager_start=True
        )

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT)
        )

    _async_start_background_discovery()
    async_track_time_interval(
        hass,
        _async_start_background_discovery,
        DISCOVERY_INTERVAL,
        cancel_on_shutdown=True,
    )
    return True


async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entities when the mac address gets discovered."""

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        if not (unique_id := entry.unique_id):
            return None
        entry_id = entry.entry_id
        entity_unique_id = entity_entry.unique_id
        entity_mac = entity_unique_id[: len(unique_id)]
        new_unique_id = None
        if entity_unique_id.startswith(entry_id):
            # Old format {entry_id}....., New format {unique_id}....
            new_unique_id = f"{unique_id}{entity_unique_id.removeprefix(entry_id)}"
        elif (
            ":" in entity_mac
            and entity_mac != unique_id
            and mac_matches_by_one(entity_mac, unique_id)
        ):
            # Old format {dhcp_mac}....., New format {discovery_mac}....
            new_unique_id = f"{unique_id}{entity_unique_id[len(unique_id):]}"
        else:
            return None
        _LOGGER.info(
            "Migrating unique_id from [%s] to [%s]",
            entity_unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await er.async_migrate_entries(hass, entry.entry_id, _async_migrator)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if entry.title != coordinator.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flux LED/MagicLight from a config entry."""
    host = entry.data[CONF_HOST]
    discovery_cached = True
    if discovery := async_get_discovery(hass, host):
        discovery_cached = False
    else:
        discovery = async_build_cached_discovery(entry)
    device: AIOWifiLedBulb = async_wifi_bulb_for_host(host, discovery=discovery)
    signal = SIGNAL_STATE_UPDATED.format(device.ipaddr)
    device.discovery = discovery
    if white_channel_type := entry.data.get(CONF_WHITE_CHANNEL_TYPE):
        device.white_channel_channel_type = NAME_TO_WHITE_CHANNEL_TYPE[
            white_channel_type
        ]

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
    if discovery_cached:
        if directed_discovery := await async_discover_device(hass, host):
            device.discovery = discovery = directed_discovery
            discovery_cached = False

    if entry.unique_id and discovery.get(ATTR_ID):
        mac = dr.format_mac(cast(str, discovery[ATTR_ID]))
        if not mac_matches_by_one(mac, entry.unique_id):
            # The device is offline and another flux_led device is now using the ip address
            raise ConfigEntryNotReady(
                f"Unexpected device found at {host}; Expected {entry.unique_id}, found"
                f" {mac}"
            )

    if not discovery_cached:
        # Only update the entry once we have verified the unique id
        # is either missing or we have verified it matches
        async_update_entry_from_discovery(
            hass, entry, discovery, device.model_num, True
        )

    await _async_migrate_unique_ids(hass, entry)

    coordinator = FluxLedUpdateCoordinator(hass, device, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    platforms = PLATFORMS_BY_TYPE[device.device_type]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    async def _async_sync_time(*args: Any) -> None:
        """Set the time every morning at 02:40:30."""
        await device.async_set_time()

    await _async_sync_time()  # set at startup
    entry.async_on_unload(async_track_time_change(hass, _async_sync_time, 3, 40, 30))

    # There must not be any awaits between here and the return
    # to avoid a race condition where the add_update_listener is not
    # in place in time for the check in async_update_entry_from_discovery
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_handle_discovered_device() -> None:
        """Handle device discovery."""
        # Force a refresh if the device is now available
        if not coordinator.last_update_success:
            coordinator.force_next_update = True
            await coordinator.async_refresh()

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            FLUX_LED_DISCOVERY_SIGNAL.format(entry_id=entry.entry_id),
            _async_handle_discovered_device,
        )
    )
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
