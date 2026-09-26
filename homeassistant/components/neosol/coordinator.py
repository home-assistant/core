"""Coordinator for the Profalux Neosol integration."""

from datetime import timedelta
from typing import override

from pyneosol import Channel, Dongle, DongleInfo, NeosolError, TransportError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type NeosolConfigEntry = ConfigEntry[NeosolCoordinator]

# The dongle only transmits, so the channel table is the one thing to read back. The
# poll is a liveness check: it tells an unplugged dongle, or a channel it no longer
# exposes, but it does not add shutters paired after the setup.
SCAN_INTERVAL = timedelta(minutes=5)


async def open_dongle(port: str) -> tuple[Dongle, DongleInfo]:
    """Open the dongle on ``port`` and read its identification.

    Opening with ``verify=False`` and reading the info explicitly keeps it to a single
    ``AT&V`` exchange, while still raising ``NotADongleError`` on an incompatible device.
    """
    dongle = await Dongle.open(port, verify=False)
    try:
        return dongle, await dongle.info()
    except BaseException:
        # Any failure, cancellation included, would otherwise leak the open port.
        await dongle.close()
        raise


class NeosolCoordinator(DataUpdateCoordinator[dict[int, Channel]]):
    """Keep track of the channels the dongle exposes, keyed by channel index."""

    config_entry: NeosolConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NeosolConfigEntry,
        dongle: Dongle,
        info: DongleInfo,
    ) -> None:
        """Initialize the coordinator around an already opened dongle."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.dongle = dongle
        self.info = info

    @override
    async def _async_update_data(self) -> dict[int, Channel]:
        """Read the paired channels from the dongle."""
        try:
            channels = await self.dongle.used_channels()
        except TransportError as err:
            # Only reopening the port recovers the link. During setup, the retry that
            # ConfigEntryNotReady triggers already does it, and a reload would loop.
            if self.config_entry.state is ConfigEntryState.LOADED:
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="lost_connection",
                translation_placeholders={"error": str(err)},
            ) from err
        except NeosolError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="channel_table_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        return {channel.index: channel for channel in channels}
