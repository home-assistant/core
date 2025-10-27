"""Bbox coordinator."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from aiobbox import BboxApi, BboxApiError, BboxAuthError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

if TYPE_CHECKING:
    from aiobbox.models import Host, Router, WANIPStats

    from . import BboxConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class BboxData:
    """Class to hold Bbox data."""

    router_info: Router
    ip_stats: WANIPStats
    # The mac address is the key
    connected_devices: dict[str, Host]


class BboxRouter(DataUpdateCoordinator[BboxData]):
    """Class to manage fetching Bbox data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BboxApi,
        config_entry: BboxConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> BboxData:
        """Fetch data from Bbox."""
        try:
            router_info = await self.client.get_router_info()
            wan_ip_stats = await self.client.get_wan_ip_stats()
            hosts = await self.client.get_hosts()

            return BboxData(
                router_info=router_info,
                ip_stats=wan_ip_stats,
                connected_devices={host.macaddress: host for host in hosts},
            )
        except BboxAuthError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_authenticate",
                translation_placeholders={"error": repr(err)},
            ) from err
        except BboxApiError as err:
            _LOGGER.error("API error fetching Bbox data: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": repr(err)},
            ) from err
        except Exception as err:
            _LOGGER.error("Unexpected error fetching Bbox data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and close client sessions."""
        await self.client.close()
        await super().async_shutdown()
