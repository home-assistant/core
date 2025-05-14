"""Service info test helpers."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo


class MockDhcpServiceInfo(DhcpServiceInfo):
    """Mocked DHCP service info."""

    def __init__(self, ip: str, hostname: str, macaddress: str) -> None:
        """Initialize the mock service info."""
        # Historically, the MAC address was formatted without colons
        # and since all consumers of this data are expecting it to be
        # formatted without colons we will continue to do so
        super().__init__(
            ip=ip,
            hostname=hostname,
            macaddress=dr.format_mac(macaddress).replace(":", ""),
        )

    async def start_discovery_flow(
        self, hass: HomeAssistant, domain: str
    ) -> ConfigFlowResult:
        """Start a reauthentication flow."""
        return await hass.config_entries.flow.async_init(
            domain, context={"source": config_entries.SOURCE_DHCP}, data=self
        )
