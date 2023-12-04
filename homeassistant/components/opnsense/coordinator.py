"""DataUpdateCoordinator for the OPNSense integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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

    hass: HomeAssistant

    url: str
    api_key: str
    api_secret: str
    verify_ssl: bool
    tracker_interfaces: list

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        url: str,
        api_key: str,
        api_secret: str,
        verify_ssl: bool,
        tracker_interfaces: list,
    ) -> None:
        """Initialize the OPNSense coordinator."""
        self.hass = hass

        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self.verify_ssl = verify_ssl
        self.tracker_interfaces = tracker_interfaces

        self.setup = False

        super().__init__(
            hass,
            _LOGGER,
            name=f"OPNSense {name}",
            update_interval=timedelta(minutes=5),  # TODO Make configurable
        )

    def _setup_clients(self, api_key, api_secret, url, verify_ssl, tracker_interfaces):
        self.interfaces_client = diagnostics.InterfaceClient(
            api_key,
            api_secret,
            url,
            verify_ssl,
            timeout=20,  # TODO Make configurable
        )

        if tracker_interfaces:
            self.netinsight_client = diagnostics.NetworkInsightClient(
                api_key,
                api_secret,
                url,
                verify_ssl,
                timeout=20,  # TODO Make configurable
            )

            # Verify that specified tracker interfaces are valid
            interfaces = list(self.netinsight_client.get_interfaces().values())
            for interface in tracker_interfaces:
                if interface not in interfaces:
                    _LOGGER.error(
                        "Specified OPNsense tracker interface %s is not found",
                        interface,
                    )
                    return False

        self.setup = True

    def _update_data(self) -> dict[str, OPNSenseResult]:
        if not self.setup:
            self._setup_clients(
                self.api_key,
                self.api_secret,
                self.url,
                self.verify_ssl,
                self.tracker_interfaces,
            )

        try:
            devices = self.interfaces_client.get_arp()
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
        except APIException:
            _LOGGER.exception("Failure while connecting to OPNsense API endpoint")
            return {}

    async def _async_update_data(self) -> dict[str, OPNSenseResult]:
        """Trigger device update check."""

        return await self.hass.async_add_executor_job(self._update_data)
