"""DataUpdateCoordinator for UniFi AP Direct."""

from datetime import timedelta
import logging
from typing import Any, override

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

from .const import DEFAULT_SSH_PORT, DOMAIN

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
        self.host_configs = self._get_host_configs(config_entry)
        self.hosts = [host_config[CONF_HOST] for host_config in self.host_configs]
        self.host = self.hosts[0] if self.hosts else config_entry.data.get(CONF_HOST)
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

    @staticmethod
    def _get_host_configs(config_entry: UniFiDirectConfigEntry) -> list[dict[str, Any]]:
        """Return configured hosts from the config entry."""
        host_entries = config_entry.data.get(CONF_HOSTS, [])

        host_configs: list[dict[str, Any]] = []
        for entry in host_entries:
            if not isinstance(entry, dict):
                continue

            host = entry.get(CONF_HOST)
            if not host:
                continue

            host_configs.append(
                {
                    CONF_HOST: str(host),
                    CONF_USERNAME: entry.get(CONF_USERNAME, ""),
                    CONF_PASSWORD: entry.get(CONF_PASSWORD, ""),
                    CONF_PORT: entry.get(CONF_PORT, DEFAULT_SSH_PORT),
                }
            )

        return host_configs

    @override
    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from the UniFi APs."""
        combined_clients: dict[str, dict] = {}
        failed_hosts: list[str] = []

        for host_config, ap in zip(self.host_configs, self.aps, strict=True):
            host = host_config[CONF_HOST]
            try:
                clients = await self.hass.async_add_executor_job(ap.get_clients)
            except UniFiAPConnectionException, UniFiAPDataException:
                failed_hosts.append(host)
                continue

            for mac, client_data in clients.items():
                combined_clients.setdefault(mac, client_data)

        if combined_clients:
            return combined_clients

        raise UpdateFailed(
            f"Failed to fetch data from UniFi APs: {', '.join(failed_hosts)}"
        )
