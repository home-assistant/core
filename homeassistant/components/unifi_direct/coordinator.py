"""DataUpdateCoordinator for UniFi AP Direct."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type UniFiDirectConfigEntry = ConfigEntry[UniFiDirectDataUpdateCoordinator]


class UniFiDirectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Class to manage fetching data from the UniFi AP."""

    config_entry: UniFiDirectConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: UniFiDirectConfigEntry
    ) -> None:
        """Initialize the coordinator using config entry."""
        self.host_configs = config_entry.data.get(CONF_HOSTS, [])
        self.hosts = [host_config[CONF_HOST] for host_config in self.host_configs]
        self.aps = [
            UniFiAP(
                target=host_config[CONF_HOST],
                username=host_config[CONF_USERNAME],
                password=host_config[CONF_PASSWORD],
                port=host_config[CONF_PORT],
            )
            for host_config in self.host_configs
        ]

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {', '.join(self.hosts)}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from the UniFi APs."""
        combined_clients: dict[str, dict] = {}
        failed_hosts: list[str] = []
        host_jobs = [
            (host_config[CONF_HOST], self.hass.async_add_executor_job(ap.get_clients))
            for host_config, ap in zip(self.host_configs, self.aps, strict=True)
        ]

        results = await asyncio.gather(
            *(job for _, job in host_jobs), return_exceptions=True
        )

        for (host, _), result in zip(host_jobs, results, strict=True):
            if isinstance(result, (UniFiAPConnectionException, UniFiAPDataException)):
                failed_hosts.append(host)
                continue
            if isinstance(result, BaseException):
                raise UpdateFailed(
                    f"Unexpected error while fetching data from UniFi AP {host}"
                ) from result
            if not isinstance(result, dict):
                raise UpdateFailed(
                    f"Unexpected client payload while fetching data from UniFi AP {host}"
                )

            for mac, client_data in result.items():
                combined_clients.setdefault(mac, client_data)

        if failed_hosts:
            raise UpdateFailed(
                f"Failed to fetch data from UniFi APs: {', '.join(failed_hosts)}"
            )

        return combined_clients
