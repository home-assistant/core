"""DataUpdateCoordinator for the OPNSense integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class OPNSenseResult:
    """Dataclass returned by the coordinator."""

    hostname: str
    ip_address: str
    mac_address: str
    manufacturer: str


class OPNSenseUpdateCoordinator(DataUpdateCoordinator[dict[str, OPNSenseResult]]):
    """The OPNSense update coordinator."""

    interfaces_client: diagnostics.InterfaceClient
    netinsight_client: diagnostics.NetworkInsightClient

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the OPNSense coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )

        self.update_interval = timedelta(
            minutes=self.config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
        )

        self.name = self.config_entry.options[CONF_NAME]
        self.url = self.config_entry.options[CONF_URL]
        self.api_key = self.config_entry.options[CONF_API_KEY]
        self.api_secret = self.config_entry.options[CONF_API_SECRET]
        self.verify_ssl = self.config_entry.options[CONF_VERIFY_SSL]
        self.tracker_interfaces = self.config_entry.options[CONF_TRACKER_INTERFACE]

        self.setup = False

    def _setup_clients(self):
        self.interfaces_client = diagnostics.InterfaceClient(
            self.api_key,
            self.api_secret,
            self.url,
            self.verify_ssl,
            timeout=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )

        if len(self.tracker_interfaces) >= 1:
            self.netinsight_client = diagnostics.NetworkInsightClient(
                self.api_key,
                self.api_secret,
                self.url,
                self.verify_ssl,
                timeout=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            )

            # Verify that specified tracker interfaces are valid
            interfaces = list(self.netinsight_client.get_interfaces().values())
            for interface in self.tracker_interfaces:
                if interface not in interfaces:
                    _LOGGER.error(
                        "Specified OPNsense tracker interface %s is not found",
                        interface,
                    )
                    return False

        self.setup = True

    def _update_data(self) -> dict[str, OPNSenseResult]:
        if not self.setup:
            self._setup_clients()

        devices = {}
        try:
            devices = self.interfaces_client.get_arp()
        except APIException as error:
            raise UpdateFailed(
                "Failure while connecting to OPNsense API endpoint"
            ) from error

        results = {}
        for device in devices:
            # Filter out non tracked interfaces
            if (len(self.tracker_interfaces) == 0) or (
                device["intf_description"] in self.tracker_interfaces
            ):
                results[device["mac"]] = OPNSenseResult(
                    hostname=device["hostname"],
                    ip_address=device["ip"],
                    mac_address=device["mac"],
                    manufacturer=device["manufacturer"],
                )

        return results

    async def _async_update_data(self) -> dict[str, OPNSenseResult]:
        """Trigger device update check."""

        return await self.hass.async_add_executor_job(self._update_data)
