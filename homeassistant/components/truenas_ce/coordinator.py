"""Data update coordinator for the TrueNAS integration."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aiotruenas import (
    NetworkInterface,
    SystemInfo,
    SystemStats,
    TrueNASAuthenticationError,
    TrueNASCallError,
    TrueNASClient,
    TrueNASError,
    TrueNASSystem,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, ERRNAME_PERMISSION_DENIED

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

type TrueNASConfigEntry = ConfigEntry[TrueNASCoordinator]


@dataclass(frozen=True, slots=True)
class TrueNASData:
    """Result of one TrueNAS poll."""

    info: SystemInfo
    interfaces: Mapping[str, NetworkInterface]
    stats: SystemStats


class TrueNASCoordinator(DataUpdateCoordinator[TrueNASData]):
    """Poll system information, network interfaces and statistics."""

    config_entry: TrueNASConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TrueNASConfigEntry,
        client: TrueNASClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        # The config flow always sets the unique_id to system.global.id.
        assert config_entry.unique_id is not None
        self.system_id = config_entry.unique_id
        self.client = client
        self.system = TrueNASSystem(client)

    @override
    async def _async_update_data(self) -> TrueNASData:
        """Fetch the latest data from TrueNAS."""
        try:
            # Reconnects after the client dropped the connection (e.g. a timeout).
            await self.client.connect()
            info = await self.system.get_system_info()
            interfaces = await self.system.get_network_interfaces()
            stats = await self.system.get_system_stats(info)
        except TrueNASAuthenticationError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except TrueNASError as err:
            if (
                isinstance(err, TrueNASCallError)
                and err.errname == ERRNAME_PERMISSION_DENIED
            ):
                raise ConfigEntryError(
                    translation_domain=DOMAIN, translation_key="permission_denied"
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return TrueNASData(info=info, interfaces=interfaces, stats=stats)
