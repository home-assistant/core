"""DataUpdateCoordinator for Meraki Dashboard."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
import logging
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    MerakiDashboardApi,
    MerakiDashboardApiAuthError,
    MerakiDashboardApiConnectionError,
    MerakiDashboardApiError,
    MerakiDashboardApiRateLimitError,
)
from .const import (
    CONF_NETWORK_ID,
    CONF_ORGANIZATION_ID,
    DEFAULT_TIMESPAN_SECONDS,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
RATE_LIMIT_ISSUE_ID = "rate_limited"


@dataclass(slots=True)
class MerakiDashboardClient:
    """Representation of a network client from Meraki."""

    mac: str
    status: str | None
    description: str | None
    dhcp_hostname: str | None
    mdns_name: str | None
    manufacturer: str | None
    ip_address: str | None
    ip6_address: str | None
    recent_device_name: str | None
    recent_device_serial: str | None
    recent_device_connection: str | None
    last_seen: int | None
    first_seen: int | None
    ssid: str | None
    vlan: str | None
    named_vlan: str | None
    switchport: str | None


@dataclass(slots=True)
class MerakiDashboardInfrastructureDevice:
    """Representation of infrastructure device from Meraki."""

    serial: str
    name: str | None
    model: str | None
    mac: str | None
    product_type: str | None
    status: str | None
    network_id: str | None
    public_ip: str | None
    lan_ip: str | None
    gateway: str | None
    ip_type: str | None
    primary_dns: str | None
    secondary_dns: str | None
    last_reported_at: str | None
    wireless_clients: int | None
    ap_enabled_ssids: int | None
    ap_channels_in_use: str | None
    ap_bands_in_use: str | None
    ap_channels_2_4ghz: str | None
    ap_channels_5ghz: str | None
    ap_channels_6ghz: str | None
    ap_channel_utilization_2_4ghz: float | None
    ap_channel_utilization_5ghz: float | None
    ap_channel_utilization_6ghz: float | None
    switch_total_ports: int | None
    switch_connected_ports: int | None
    switch_connected_clients: int | None
    switch_active_poe_ports: int | None
    appliance_clients: int | None
    appliance_performance_score: float | None


@dataclass(slots=True)
class MerakiDashboardData:
    """Combined data model for Meraki Dashboard integration."""

    clients: dict[str, MerakiDashboardClient]
    infrastructure_devices: dict[str, MerakiDashboardInfrastructureDevice]


type MerakiDashboardConfigEntry = ConfigEntry[MerakiDashboardDataUpdateCoordinator]


class MerakiDashboardDataUpdateCoordinator(DataUpdateCoordinator[MerakiDashboardData]):
    """Coordinate Meraki Dashboard updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MerakiDashboardConfigEntry,
        api: MerakiDashboardApi,
        *,
        track_clients: bool,
        track_bluetooth_clients: bool,
        track_infrastructure_devices: bool,
        included_clients: set[str],
    ) -> None:
        """Initialize coordinator."""
        self.api = api
        self.network_id = config_entry.data[CONF_NETWORK_ID]
        self.organization_id = config_entry.data[CONF_ORGANIZATION_ID]
        self.track_clients = track_clients
        self.track_bluetooth_clients = track_bluetooth_clients
        self.track_infrastructure_devices = track_infrastructure_devices
        self.included_clients = included_clients
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> MerakiDashboardData:
        """Fetch latest data from API endpoint."""
        try:
            clients: list[dict[str, Any]] = []
            bluetooth_clients: list[dict[str, Any]] = []
            if self.track_clients and self.track_bluetooth_clients:
                clients, bluetooth_clients = await asyncio.gather(
                    self.api.async_get_network_clients(
                        self.network_id,
                        timespan=DEFAULT_TIMESPAN_SECONDS,
                    ),
                    self.api.async_get_network_bluetooth_clients(
                        self.network_id,
                        timespan=DEFAULT_TIMESPAN_SECONDS,
                    ),
                )
            elif self.track_clients:
                clients = await self.api.async_get_network_clients(
                    self.network_id,
                    timespan=DEFAULT_TIMESPAN_SECONDS,
                )
            elif self.track_bluetooth_clients:
                bluetooth_clients = await self.api.async_get_network_bluetooth_clients(
                    self.network_id,
                    timespan=DEFAULT_TIMESPAN_SECONDS,
                )

            device_statuses: list[dict[str, Any]] = []
            if self.track_infrastructure_devices:
                device_statuses = (
                    await self.api.async_get_organization_devices_statuses(
                        self.organization_id
                    )
                )
            ir.async_delete_issue(self.hass, DOMAIN, RATE_LIMIT_ISSUE_ID)
        except MerakiDashboardApiAuthError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except MerakiDashboardApiRateLimitError as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                RATE_LIMIT_ISSUE_ID,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=RATE_LIMIT_ISSUE_ID,
            )
            raise UpdateFailed("Meraki API rate limit reached") from err
        except MerakiDashboardApiConnectionError as err:
            raise UpdateFailed("Cannot connect") from err
        except MerakiDashboardApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        mapped_clients: dict[str, MerakiDashboardClient] = {}
        for client in clients:
            mac_address = format_mac(client.get("mac", ""))
            if not mac_address:
                continue
            if self.included_clients and mac_address not in self.included_clients:
                continue

            mapped_clients[mac_address] = MerakiDashboardClient(
                mac=mac_address,
                status=client.get("status"),
                description=client.get("description"),
                dhcp_hostname=client.get("dhcpHostname"),
                mdns_name=client.get("mdnsName"),
                manufacturer=client.get("manufacturer"),
                ip_address=client.get("ip"),
                ip6_address=client.get("ip6"),
                recent_device_name=client.get("recentDeviceName"),
                recent_device_serial=client.get("recentDeviceSerial"),
                recent_device_connection=client.get("recentDeviceConnection"),
                last_seen=client.get("lastSeen"),
                first_seen=client.get("firstSeen"),
                ssid=client.get("ssid"),
                vlan=client.get("vlan"),
                named_vlan=client.get("namedVlan"),
                switchport=client.get("switchport"),
            )

        for bluetooth_client in bluetooth_clients:
            mac_address = format_mac(bluetooth_client.get("mac", ""))
            if not mac_address:
                continue
            if self.included_clients and mac_address not in self.included_clients:
                continue

            existing_client = mapped_clients.get(mac_address)
            bluetooth_name = bluetooth_client.get("name") or bluetooth_client.get(
                "deviceName"
            )
            bluetooth_last_seen = bluetooth_client.get("lastSeen")
            if existing_client is not None:
                existing_client.status = "Online"
                if not existing_client.description:
                    existing_client.description = bluetooth_name
                if not existing_client.manufacturer:
                    existing_client.manufacturer = bluetooth_client.get("manufacturer")
                if (
                    isinstance(existing_client.last_seen, int)
                    and isinstance(bluetooth_last_seen, int)
                    and bluetooth_last_seen > existing_client.last_seen
                ) or (
                    existing_client.last_seen is None
                    and isinstance(bluetooth_last_seen, int)
                ):
                    existing_client.last_seen = bluetooth_last_seen
                if not existing_client.recent_device_connection:
                    existing_client.recent_device_connection = "Bluetooth"
                continue

            mapped_clients[mac_address] = MerakiDashboardClient(
                mac=mac_address,
                status="Online",
                description=bluetooth_name,
                dhcp_hostname=None,
                mdns_name=bluetooth_client.get("deviceName"),
                manufacturer=bluetooth_client.get("manufacturer"),
                ip_address=None,
                ip6_address=None,
                recent_device_name=None,
                recent_device_serial=None,
                recent_device_connection="Bluetooth",
                last_seen=bluetooth_last_seen,
                first_seen=None,
                ssid=None,
                vlan=None,
                named_vlan=None,
                switchport=None,
            )

        raw_infrastructure_devices: dict[str, dict[str, Any]] = {}
        for device in device_statuses:
            serial = device.get("serial")
            if not serial or device.get("networkId") != self.network_id:
                continue

            product_type = device.get("productType")
            if product_type not in {"switch", "appliance", "wireless"}:
                continue

            raw_infrastructure_devices[serial] = device

        infrastructure_details = await self._async_fetch_infrastructure_details(
            raw_infrastructure_devices
        )

        mapped_devices = {
            serial: MerakiDashboardInfrastructureDevice(
                serial=serial,
                name=device.get("name"),
                model=device.get("model"),
                mac=format_mac(device.get("mac", "")) or None,
                product_type=cast(str | None, device.get("productType")),
                status=device.get("status"),
                network_id=device.get("networkId"),
                public_ip=device.get("publicIp"),
                lan_ip=device.get("lanIp"),
                gateway=device.get("gateway"),
                ip_type=device.get("ipType"),
                primary_dns=device.get("primaryDns"),
                secondary_dns=device.get("secondaryDns"),
                last_reported_at=device.get("lastReportedAt"),
                wireless_clients=infrastructure_details.get(serial, {}).get(
                    "wireless_clients"
                ),
                ap_enabled_ssids=infrastructure_details.get(serial, {}).get(
                    "ap_enabled_ssids"
                ),
                ap_channels_in_use=infrastructure_details.get(serial, {}).get(
                    "ap_channels_in_use"
                ),
                ap_bands_in_use=infrastructure_details.get(serial, {}).get(
                    "ap_bands_in_use"
                ),
                ap_channels_2_4ghz=infrastructure_details.get(serial, {}).get(
                    "ap_channels_2_4ghz"
                ),
                ap_channels_5ghz=infrastructure_details.get(serial, {}).get(
                    "ap_channels_5ghz"
                ),
                ap_channels_6ghz=infrastructure_details.get(serial, {}).get(
                    "ap_channels_6ghz"
                ),
                ap_channel_utilization_2_4ghz=infrastructure_details.get(
                    serial, {}
                ).get("ap_channel_utilization_2_4ghz"),
                ap_channel_utilization_5ghz=infrastructure_details.get(serial, {}).get(
                    "ap_channel_utilization_5ghz"
                ),
                ap_channel_utilization_6ghz=infrastructure_details.get(serial, {}).get(
                    "ap_channel_utilization_6ghz"
                ),
                switch_total_ports=infrastructure_details.get(serial, {}).get(
                    "switch_total_ports"
                ),
                switch_connected_ports=infrastructure_details.get(serial, {}).get(
                    "switch_connected_ports"
                ),
                switch_connected_clients=infrastructure_details.get(serial, {}).get(
                    "switch_connected_clients"
                ),
                switch_active_poe_ports=infrastructure_details.get(serial, {}).get(
                    "switch_active_poe_ports"
                ),
                appliance_clients=infrastructure_details.get(serial, {}).get(
                    "appliance_clients"
                ),
                appliance_performance_score=infrastructure_details.get(serial, {}).get(
                    "appliance_performance_score"
                ),
            )
            for serial, device in raw_infrastructure_devices.items()
        }

        return MerakiDashboardData(
            clients=mapped_clients,
            infrastructure_devices=mapped_devices,
        )

    async def _async_fetch_infrastructure_details(
        self, devices: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Fetch infrastructure details by product type."""
        details: dict[str, dict[str, Any]] = {serial: {} for serial in devices}
        wireless_channel_utilization = (
            await self._async_get_wireless_channel_utilization(devices)
        )

        tasks: list[Awaitable[None]] = []
        for serial, device in devices.items():
            match device.get("productType"):
                case "wireless":
                    tasks.append(
                        self._async_fetch_wireless_details(
                            serial, details, wireless_channel_utilization
                        )
                    )
                case "switch":
                    tasks.append(self._async_fetch_switch_details(serial, details))
                case "appliance":
                    tasks.append(self._async_fetch_appliance_details(serial, details))

        if tasks:
            await asyncio.gather(*tasks)

        return details

    async def _async_get_wireless_channel_utilization(
        self, devices: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, float]]:
        """Fetch wireless channel utilization for wireless devices."""
        if not any(
            device.get("productType") == "wireless" for device in devices.values()
        ):
            return {}

        try:
            utilization_entries = await (
                self.api.async_get_organization_wireless_channel_utilization_by_device(
                    self.organization_id,
                    self.network_id,
                    timespan=DEFAULT_TIMESPAN_SECONDS,
                )
            )
        except MerakiDashboardApiAuthError:
            raise
        except (MerakiDashboardApiConnectionError, MerakiDashboardApiError) as err:
            _LOGGER.debug("Unable to fetch channel utilization data: %s", err)
            return {}

        return self._parse_wireless_channel_utilization(utilization_entries)

    def _parse_wireless_channel_utilization(
        self, utilization_entries: list[dict[str, Any]]
    ) -> dict[str, dict[str, float]]:
        """Parse wireless utilization response indexed by serial and band."""
        wireless_channel_utilization: dict[str, dict[str, float]] = {}

        for entry in utilization_entries:
            serial = entry.get("serial")
            if not isinstance(serial, str):
                continue
            by_band = entry.get("byBand")
            if not isinstance(by_band, list):
                continue

            band_data: dict[str, float] = {}
            for band_entry in by_band:
                if not isinstance(band_entry, dict):
                    continue
                band = band_entry.get("band")
                if not isinstance(band, str):
                    continue
                total = band_entry.get("total")
                percentage = (
                    total.get("percentage") if isinstance(total, dict) else None
                )
                if isinstance(percentage, int | float):
                    band_data[band] = float(percentage)

            if band_data:
                wireless_channel_utilization[serial] = band_data

        return wireless_channel_utilization

    async def _async_fetch_wireless_details(
        self,
        serial: str,
        details: dict[str, dict[str, Any]],
        wireless_channel_utilization: dict[str, dict[str, float]],
    ) -> None:
        """Fetch optional details for a wireless device."""
        if (
            clients := await self._async_call_optional(
                serial,
                "device clients",
                self.api.async_get_device_clients(
                    serial, timespan=DEFAULT_TIMESPAN_SECONDS
                ),
            )
        ) is not None:
            details[serial]["wireless_clients"] = len(clients)

        if (
            status := await self._async_call_optional(
                serial,
                "wireless status",
                self.api.async_get_device_wireless_status(serial),
            )
        ) is None:
            return

        enabled_sets = self._extract_enabled_service_sets(status)
        details[serial]["ap_enabled_ssids"] = len(enabled_sets)

        if channels := self._format_channels(enabled_sets):
            details[serial]["ap_channels_in_use"] = channels
        if bands := self._format_bands(enabled_sets):
            details[serial]["ap_bands_in_use"] = bands

        for band_name, details_key in (
            ("2.4", "ap_channels_2_4ghz"),
            ("5", "ap_channels_5ghz"),
            ("6", "ap_channels_6ghz"),
        ):
            if channels_for_band := self._format_channels(enabled_sets, band_name):
                details[serial][details_key] = channels_for_band

        self._apply_channel_utilization(
            details[serial], wireless_channel_utilization.get(serial)
        )

    def _extract_enabled_service_sets(
        self, status: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return enabled service sets from the wireless status payload."""
        service_sets = status.get("basicServiceSets")
        if not isinstance(service_sets, list):
            return []
        return [
            entry
            for entry in service_sets
            if isinstance(entry, dict) and entry.get("enabled") is True
        ]

    def _format_channels(
        self, enabled_sets: list[dict[str, Any]], band_name: str | None = None
    ) -> str | None:
        """Format unique channels from enabled SSIDs."""
        channels = sorted(
            {
                str(channel)
                for entry in enabled_sets
                if (channel := entry.get("channel")) is not None
                and (
                    band_name is None
                    or (
                        isinstance(entry.get("band"), str)
                        and cast(str, entry["band"]).startswith(band_name)
                    )
                )
            },
            key=int,
        )
        if not channels:
            return None
        return ", ".join(channels)

    def _format_bands(self, enabled_sets: list[dict[str, Any]]) -> str | None:
        """Format unique bands from enabled SSIDs."""
        bands = sorted(
            {
                str(band)
                for entry in enabled_sets
                if (band := entry.get("band")) is not None
            }
        )
        if not bands:
            return None
        return ", ".join(bands)

    def _apply_channel_utilization(
        self, device_details: dict[str, Any], band_utilization: dict[str, float] | None
    ) -> None:
        """Apply channel utilization values for known bands."""
        if not band_utilization:
            return
        if "2.4" in band_utilization:
            device_details["ap_channel_utilization_2_4ghz"] = band_utilization["2.4"]
        if "5" in band_utilization:
            device_details["ap_channel_utilization_5ghz"] = band_utilization["5"]
        if "6" in band_utilization:
            device_details["ap_channel_utilization_6ghz"] = band_utilization["6"]

    async def _async_fetch_switch_details(
        self, serial: str, details: dict[str, dict[str, Any]]
    ) -> None:
        """Fetch optional details for a switch device."""
        if (
            ports := await self._async_call_optional(
                serial,
                "switch port statuses",
                self.api.async_get_device_switch_ports_statuses(
                    serial, timespan=DEFAULT_TIMESPAN_SECONDS
                ),
            )
        ) is None:
            return

        details[serial]["switch_total_ports"] = len(ports)
        details[serial]["switch_connected_ports"] = sum(
            1 for port in ports if port.get("status") == "Connected"
        )
        details[serial]["switch_connected_clients"] = sum(
            client_count
            for port in ports
            if isinstance((client_count := port.get("clientCount")), int)
        )
        details[serial]["switch_active_poe_ports"] = sum(
            1
            for port in ports
            if isinstance(port.get("poe"), dict)
            and port["poe"].get("isAllocated") is True
        )

    async def _async_fetch_appliance_details(
        self, serial: str, details: dict[str, dict[str, Any]]
    ) -> None:
        """Fetch optional details for an appliance device."""
        if (
            clients := await self._async_call_optional(
                serial,
                "device clients",
                self.api.async_get_device_clients(
                    serial, timespan=DEFAULT_TIMESPAN_SECONDS
                ),
            )
        ) is not None:
            details[serial]["appliance_clients"] = len(clients)

        if (
            performance := await self._async_call_optional(
                serial,
                "appliance performance",
                self.api.async_get_device_appliance_performance(serial),
            )
        ) is None:
            return

        perf_score = performance.get("perfScore")
        if isinstance(perf_score, float | int):
            details[serial]["appliance_performance_score"] = float(perf_score)

    async def _async_call_optional(
        self,
        serial: str,
        endpoint: str,
        coro: Awaitable[Any],
    ) -> Any | None:
        """Call optional endpoint and suppress non-auth errors."""
        try:
            return await coro
        except MerakiDashboardApiAuthError:
            raise
        except (MerakiDashboardApiConnectionError, MerakiDashboardApiError) as err:
            _LOGGER.debug("Unable to fetch %s for device %s: %s", endpoint, serial, err)
            return None
