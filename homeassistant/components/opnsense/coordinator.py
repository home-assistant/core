"""OPNsense Coordinator."""

from collections.abc import Callable, Mapping, MutableMapping
import copy
from datetime import timedelta
import logging
import time
from typing import Any

from aiopnsense import OPNsenseClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_UNBOUND_BLOCKLIST,
    CONF_SYNC_CARP,
    CONF_SYNC_CERTIFICATES,
    CONF_SYNC_DHCP_LEASES,
    CONF_SYNC_FIREWALL_AND_NAT,
    CONF_SYNC_FIRMWARE_UPDATES,
    CONF_SYNC_GATEWAYS,
    CONF_SYNC_INTERFACES,
    CONF_SYNC_NOTICES,
    CONF_SYNC_SERVICES,
    CONF_SYNC_SPEEDTEST,
    CONF_SYNC_TELEMETRY,
    CONF_SYNC_UNBOUND,
    CONF_SYNC_VNSTAT,
    CONF_SYNC_VPN,
    DEFAULT_SYNC_OPTION_VALUE,
    DOMAIN,
)
from .helpers import dict_get

_LOGGER: logging.Logger = logging.getLogger(__name__)


class OPNsenseDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator class for OPNsense."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OPNsenseClient,
        name: str,
        update_interval: timedelta,
        device_unique_id: str,
        config_entry: ConfigEntry,
        device_tracker_coordinator: bool = False,
    ) -> None:
        """Initialize the data object."""
        _LOGGER.info(
            "Initializing OPNsense Data Update Coordinator %s",
            "for Device Tracker" if device_tracker_coordinator else "",
        )
        if config_entry is None:
            raise ValueError(
                "config_entry is required for OPNsenseDataUpdateCoordinator"
            )
        self._client: OPNsenseClient = client
        self._state: dict[str, Any] = {}
        self._device_tracker_coordinator: bool = device_tracker_coordinator
        self._mismatched_count = 0
        self._device_unique_id: str = device_unique_id
        self._updating: bool = False
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self._categories = self._build_categories()

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        _LOGGER.debug(
            "Setting up %sCoordinator",
            "DT " if self._device_tracker_coordinator else "",
        )

    async def _get_states(self, categories: list) -> dict[str, Any]:
        state: dict[str, Any] = {}
        total_time: float = 0
        for cat in categories:
            method_name: str = cat.get("function", "")
            method: Callable | None = getattr(self._client, method_name, None)
            if method is not None:
                start_time: float = time.perf_counter()
                if method_name == "get_device_unique_id":
                    state[cat.get("state_key")] = await method(
                        expected_id=self._device_unique_id
                    )
                else:
                    state[cat.get("state_key")] = await method()
                end_time: float = time.perf_counter()
                elapsed_time: float = end_time - start_time
                total_time += elapsed_time
                _LOGGER.debug(
                    "[%sCoordinator Timing] %s: %.3f seconds",
                    "DT " if self._device_tracker_coordinator else "",
                    cat.get("function", ""),
                    elapsed_time,
                )
            else:
                _LOGGER.error("Method %s not found", cat.get("function", ""))

        return state

    def _build_categories(self) -> list[dict[str, str]]:
        """Build the categories for fetching data."""
        if not self.config_entry:
            _LOGGER.error("Coordinator build_categories failed. No config entry found")
            return []
        config: Mapping[str, Any] = self.config_entry.data
        categories: list[dict[str, str]] = [
            {"function": "get_device_unique_id", "state_key": "device_unique_id"},
            {"function": "get_system_info", "state_key": "system_info"},
            {
                "function": "get_host_firmware_version",
                "state_key": "host_firmware_version",
            },
        ]

        if config.get(CONF_SYNC_TELEMETRY, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_telemetry", "state_key": "telemetry"})
        if config.get(CONF_SYNC_VNSTAT, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_vnstat", "state_key": "vnstat"})
        if config.get(CONF_SYNC_SPEEDTEST, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_speedtest", "state_key": "speedtest"})
        if config.get(CONF_SYNC_VPN, DEFAULT_SYNC_OPTION_VALUE):
            categories.extend(
                [
                    {"function": "get_openvpn", "state_key": "openvpn"},
                    {"function": "get_wireguard", "state_key": "wireguard"},
                ]
            )

        if config.get(CONF_SYNC_FIRMWARE_UPDATES, DEFAULT_SYNC_OPTION_VALUE):
            categories.append(
                {
                    "function": "get_firmware_update_info",
                    "state_key": "firmware_update_info",
                }
            )

        if config.get(CONF_SYNC_CARP, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_carp", "state_key": "carp"})
        if config.get(CONF_SYNC_DHCP_LEASES, DEFAULT_SYNC_OPTION_VALUE):
            categories.append(
                {"function": "get_dhcp_leases", "state_key": "dhcp_leases"}
            )
        if config.get(CONF_SYNC_GATEWAYS, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_gateways", "state_key": "gateways"})
        if config.get(CONF_SYNC_SERVICES, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_services", "state_key": "services"})
        if config.get(CONF_SYNC_NOTICES, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_notices", "state_key": "notices"})
        if config.get(CONF_SYNC_FIREWALL_AND_NAT, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_firewall", "state_key": "firewall"})
        if config.get(CONF_SYNC_UNBOUND, DEFAULT_SYNC_OPTION_VALUE):
            categories.append(
                {
                    "function": "get_unbound_blocklist",
                    "state_key": ATTR_UNBOUND_BLOCKLIST,
                }
            )
        if config.get(CONF_SYNC_INTERFACES, DEFAULT_SYNC_OPTION_VALUE):
            categories.append({"function": "get_interfaces", "state_key": "interfaces"})
        if config.get(CONF_SYNC_CERTIFICATES, DEFAULT_SYNC_OPTION_VALUE):
            categories.append(
                {"function": "get_certificates", "state_key": "certificates"}
            )
        _LOGGER.debug(
            "Categories for fetching data: %s",
            [item["state_key"] for item in categories],
        )
        return categories

    async def _check_device_unique_id(self) -> bool:
        """Check if the device unique ID matches the one in the config."""
        if self._state.get("device_unique_id") is None:
            _LOGGER.warning(
                "Coordinator failed to confirm OPNsense Router Unique ID. Will retry"
            )
            self._mismatched_count = 0
            return False
        if self._state.get("device_unique_id") != self._device_unique_id:
            _LOGGER.debug(
                "[Coordinator async_update_data]: config device id: %s, router device id: %s",
                self._device_unique_id,
                self._state.get("device_unique_id"),
            )
            _LOGGER.error(
                "Coordinator error. "
                "OPNsense Router Device ID (%s) differs from the one saved in the OPNsense integration (%s)",
                self._state.get("device_unique_id"),
                self._device_unique_id,
            )
            self._mismatched_count += 1
            # Trigger repair task and shutdown if this happens 3 times in a row
            if self._mismatched_count == 3:
                ir.async_create_issue(
                    hass=self.hass,
                    domain=DOMAIN,
                    issue_id=f"{self._device_unique_id}_device_id_mismatched",
                    is_fixable=False,
                    is_persistent=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="device_id_mismatched",
                )
                _LOGGER.error(
                    "OPNsense Device ID has changed which indicates new or changed hardware. "
                    "In order to accommodate this, the OPNsense integration needs to be removed and reinstalled for this router. "
                    "The OPNsense integration is shutting down"
                )
                await self.async_shutdown()
            return False
        self._mismatched_count = 0
        return True

    async def _async_update_dt_data(self) -> dict[str, Any]:
        """Update data for device tracker."""
        categories: list = [
            {"function": "get_device_unique_id", "state_key": "device_unique_id"},
            {
                "function": "get_host_firmware_version",
                "state_key": "host_firmware_version",
            },
            {"function": "get_system_info", "state_key": "system_info"},
            {
                "function": "get_arp_table",
                "state_key": "arp_table",
            },
        ]
        self._state.update(await self._get_states(categories))
        if self._state.get("device_unique_id") is None:
            _LOGGER.warning(
                "Coordinator failed to confirm OPNsense Router Unique ID. Will retry"
            )
            return {}
        if self._state.get("device_unique_id") != self._device_unique_id:
            _LOGGER.error(
                "Coordinator error. OPNsense Router Device ID (%s) differs from the one saved in the OPNsense integration (%s)",
                self._state.get("device_unique_id"),
                self._device_unique_id,
            )
            return {}
        query_count = await self._client.get_query_counts()
        _LOGGER.debug("DT Update Complete. API Queries: %s", query_count)
        return self._state

    async def _calculate_vpn_speeds(self, elapsed_time: float) -> None:
        for vpn_type in ("openvpn", "wireguard"):
            cs = ["servers"]
            if vpn_type == "wireguard":
                cs = ["clients", "servers"]
            for clients_servers in cs:
                for instance_name in (
                    dict_get(self._state, f"{vpn_type}.{clients_servers}", {}) or {}
                ):
                    previous_clients_servers = dict_get(
                        self._state,
                        f"previous_state.{vpn_type}.{clients_servers}",
                        {},
                    )
                    if (
                        not isinstance(previous_clients_servers, MutableMapping)
                        or instance_name not in previous_clients_servers
                    ):
                        continue

                    instance: dict[str, Any] = (
                        self._state.get(vpn_type, {})
                        .get(clients_servers, {})
                        .get(instance_name, {})
                    )
                    previous_instance: dict[str, Any] = (
                        self._state.get("previous_state", {})
                        .get(vpn_type, {})
                        .get(clients_servers, {})
                        .get(instance_name, {})
                    )

                    for prop_name in (
                        "total_bytes_recv",
                        "total_bytes_sent",
                    ):
                        if "pkts" in prop_name or "bytes" in prop_name:
                            (
                                new_property,
                                value,
                            ) = await OPNsenseDataUpdateCoordinator._calculate_speed(
                                prop_name=prop_name,
                                elapsed_time=elapsed_time,
                                current_parent_value=instance[prop_name],
                                previous_parent_value=previous_instance[prop_name],
                            )

                        instance[new_property] = value

    async def _calculate_interface_speeds(self, elapsed_time: float) -> None:
        for interface_name, interface in (
            dict_get(self._state, "interfaces", {}) or {}
        ).items():
            previous_interface = dict_get(
                self._state,
                f"previous_state.interfaces.{interface_name}",
            )
            if previous_interface is None:
                continue

            for prop_name in (
                "inbytes",
                "outbytes",
                "inpkts",
                "outpkts",
            ):
                if "pkts" in prop_name or "bytes" in prop_name:
                    (
                        new_property,
                        value,
                    ) = await OPNsenseDataUpdateCoordinator._calculate_speed(
                        prop_name=prop_name,
                        elapsed_time=elapsed_time,
                        current_parent_value=interface[prop_name],
                        previous_parent_value=previous_interface[prop_name],
                    )

                    interface[new_property] = value

    async def _calculate_entity_speeds(self) -> None:
        """Calculate speeds for interfaces and VPNs."""
        update_time = dict_get(self._state, "update_time")
        previous_update_time = dict_get(self._state, "previous_state.update_time")
        if not previous_update_time or not self.config_entry:
            return

        elapsed_time: float = update_time - previous_update_time
        config: Mapping[str, Any] = self.config_entry.data

        if config.get(CONF_SYNC_INTERFACES, DEFAULT_SYNC_OPTION_VALUE):
            await self._calculate_interface_speeds(elapsed_time=elapsed_time)

        if config.get(CONF_SYNC_VPN, DEFAULT_SYNC_OPTION_VALUE):
            await self._calculate_vpn_speeds(elapsed_time=elapsed_time)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest state from OPNsense."""
        if self._updating:
            _LOGGER.warning(
                "Skipping %supdate because the previous update is still in progress",
                "DT " if self._device_tracker_coordinator else "",
            )
            return self._state
        self._updating = True

        try:
            _LOGGER.info(
                "%sUpdating Data",
                "DT " if self._device_tracker_coordinator else "",
            )
            await self._client.reset_query_counts()

            previous_state: dict[str, Any] = copy.deepcopy(self._state)
            if "previous_state" in previous_state:
                del previous_state["previous_state"]

            # ensure clean state each interval
            self._state = {}
            self._state["update_time"] = time.time()
            self._state["previous_state"] = previous_state

            if self._device_tracker_coordinator:
                return await self._async_update_dt_data()

            self._state.update(await self._get_states(self._categories))

            if not await self._check_device_unique_id():
                return {}

            await self._calculate_entity_speeds()

            query_count = await self._client.get_query_counts()
            _LOGGER.debug("Update Complete. API Queries: %s", query_count)
        except Exception as err:
            raise UpdateFailed(f"Failed to refresh OPNsense data: {err}") from err
        else:
            return self._state
        finally:
            self._updating = False

    @staticmethod
    async def _calculate_speed(
        prop_name: str,
        elapsed_time: float,
        current_parent_value: float,
        previous_parent_value: float,
    ) -> tuple[str, int]:
        try:
            change: float = abs(current_parent_value - previous_parent_value)
            rate: float = change / elapsed_time
        except TypeError, KeyError, ZeroDivisionError:
            rate = 0

        value: float = 0
        if "pkts" in prop_name:
            label = "packets_per_second"
            value = rate
        elif "bytes" in prop_name:
            label = "kilobytes_per_second"
            # 1 Byte = 8 bits
            # 1 byte is equal to 0.001 kilobytes
            KBs: float = rate / 1000
            # Kbs = KBs * 8
            value = KBs
        new_property: str = f"{prop_name}_{label}"
        value = round(value)
        return new_property, value
