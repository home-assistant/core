"""The Kaleidescape integration."""

from __future__ import annotations

from dataclasses import dataclass

from kaleidescape import Device as KaleidescapeDevice, KaleidescapeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE, Platform.SENSOR]

type KaleidescapeConfigEntry = ConfigEntry[KaleidescapeDevice]


async def async_setup_entry(
    hass: HomeAssistant, entry: KaleidescapeConfigEntry
) -> bool:
    """Set up Kaleidescape from a config entry."""
    device = KaleidescapeDevice(
        entry.data[CONF_HOST], timeout=5, reconnect=True, reconnect_delay=5
    )

    try:
        await device.connect()
    except (KaleidescapeError, ConnectionError) as err:
        await device.disconnect()
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.data[CONF_HOST]}: {err}"
        ) from err

    entry.runtime_data = device

    async def disconnect(event: Event) -> None:
        await device.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )
    entry.async_on_unload(device.disconnect)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: KaleidescapeConfigEntry
) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@dataclass
class KaleidescapeDeviceInfo:
    """Metadata for a Kaleidescape device."""

    host: str
    serial: str
    name: str
    model: str
    server_only: bool


class UnsupportedError(HomeAssistantError):
    """Error for unsupported device types."""


async def validate_host(host: str) -> KaleidescapeDeviceInfo:
    """Validate device host."""
    device = KaleidescapeDevice(host)

    try:
        await device.connect()
    except (KaleidescapeError, ConnectionError):
        await device.disconnect()
        raise

    info = KaleidescapeDeviceInfo(
        host=device.host,
        serial=device.system.serial_number,
        name=device.system.friendly_name,
        model=device.system.type,
        server_only=device.is_server_only,
    )

    await device.disconnect()

    return info
