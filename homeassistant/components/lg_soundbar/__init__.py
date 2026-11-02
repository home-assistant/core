"""The lg_soundbar component."""

from ipaddress import ip_address
from typing import override

from aiotemescal import TemescalClient
from zeroconf import DNSAddress, RecordUpdate, RecordUpdateListener, Zeroconf

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.MEDIA_PLAYER]

type LGSoundbarConfigEntry = ConfigEntry[TemescalClient]


class AnnouncementListener(RecordUpdateListener):
    """Reconnect as soon as the soundbar announces its address over mDNS.

    Records already in the cache produce no browser event, so a device that
    boots again with the same data is only seen at the record level.
    """

    def __init__(self, client: TemescalClient, address: bytes) -> None:
        """Initialize the listener."""
        self._client = client
        self._address = address

    @override
    def async_update_records(
        self, zc: Zeroconf, now: float, records: list[RecordUpdate]
    ) -> None:
        """Wake the client up when a record carries the address of the device."""
        if self._client.connected:
            return
        for update in records:
            if (
                isinstance(record := update.new, DNSAddress)
                and record.address == self._address
            ):
                self._client.reconnect_now()
                return


async def async_setup_entry(hass: HomeAssistant, entry: LGSoundbarConfigEntry) -> None:
    """Set up platform from a ConfigEntry."""
    client = TemescalClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    entry.runtime_data = client
    entry.async_on_unload(client.stop)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Soundbars are often unplugged, so the client keeps reconnecting in the
    # background instead of failing the setup while the device is unreachable
    await client.start()

    if (address := _packed_address(entry.data[CONF_HOST])) is not None:
        aiozc = await zeroconf.async_get_async_instance(hass)
        listener = AnnouncementListener(client, address)
        aiozc.zeroconf.async_add_listener(listener, None)
        entry.async_on_unload(lambda: aiozc.zeroconf.async_remove_listener(listener))


def _packed_address(host: str) -> bytes | None:
    """Return the address as found in mDNS records, None for a hostname."""
    try:
        return ip_address(host).packed
    except ValueError:
        return None


async def async_unload_entry(hass: HomeAssistant, entry: LGSoundbarConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
