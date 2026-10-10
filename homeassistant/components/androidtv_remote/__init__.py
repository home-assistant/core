"""The Android TV Remote integration."""

from asyncio import timeout
import logging

from androidtvremote2 import CannotConnect, ConnectionClosed, InvalidAuth

from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .helpers import (
    AndroidTVRemoteConfigEntry,
    async_get_nic_mac_address,
    create_api,
    get_enable_ime,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.REMOTE]


async def async_setup_entry(
    hass: HomeAssistant, entry: AndroidTVRemoteConfigEntry
) -> bool:
    """Set up Android TV Remote from a config entry."""
    _LOGGER.debug("async_setup_entry: %s", entry.data)
    api = create_api(hass, entry.data[CONF_HOST], get_enable_ime(entry))

    @callback
    def is_available_updated(is_available: bool) -> None:
        _LOGGER.info(
            "%s %s at %s",
            "Reconnected to" if is_available else "Disconnected from",
            entry.data[CONF_NAME],
            entry.data[CONF_HOST],
        )

    api.add_is_available_updated_callback(is_available_updated)

    try:
        async with timeout(5.0):
            await api.async_connect()
    except InvalidAuth as exc:
        # The Android TV is hard reset or the certificate and key files were deleted.
        raise ConfigEntryAuthFailed from exc
    except (CannotConnect, ConnectionClosed, TimeoutError) as exc:
        # The Android TV is network unreachable. Raise exception and
        # let Home Assistant retry later. If device gets a new IP
        # address the zeroconf flow will update the config.
        raise ConfigEntryNotReady from exc

    def reauth_needed() -> None:
        """Start a reauth flow if Android TV is hard reset while reconnecting."""
        entry.async_start_reauth(hass)

    # Start a task (canceled in disconnect) to keep reconnecting if device becomes
    # network unreachable. If device gets a new IP address the zeroconf flow will
    # update the config entry data and reload the config entry.
    api.keep_reconnecting(reauth_needed)

    # Resolve physical NIC MAC address (Wi-Fi or Ethernet) to link with router device trackers
    assert entry.unique_id is not None
    connections = {(dr.CONNECTION_NETWORK_MAC, entry.data[CONF_MAC])}
    if nic_mac := await async_get_nic_mac_address(hass, entry.data[CONF_HOST]):
        connections.add((dr.CONNECTION_NETWORK_MAC, nic_mac))

    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get_device_by_identifier(
        (DOMAIN, entry.unique_id), entry.entry_id
    ):
        if nic_mac:
            dev_reg.async_update_device(
                device.id,
                new_connections=connections,
            )
    elif api.device_info is not None:
        device_info = api.device_info
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.unique_id)},
            connections=connections,
            manufacturer=device_info["manufacturer"],
            model=device_info["model"],
            name=entry.data[CONF_NAME],
        )

    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def on_hass_stop(event: Event) -> None:
        """Stop push updates when hass stops."""
        api.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )
    entry.async_on_unload(api.disconnect)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AndroidTVRemoteConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry: %s", entry.data)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
