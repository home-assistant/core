"""Config flow for Shelly integration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, cast

from aioshelly.ble import get_name_from_model_id
from aioshelly.ble.manufacturer_data import (
    has_rpc_over_ble,
    parse_shelly_manufacturer_data,
)
from aioshelly.block_device import BlockDevice
from aioshelly.common import ConnectionOptions, get_info
from aioshelly.const import BLOCK_GENERATIONS, DEFAULT_HTTP_PORT, RPC_GENERATIONS
from aioshelly.exceptions import (
    CustomPortNotSupported,
    DeviceConnectionError,
    InvalidAuthError,
    InvalidHostError,
    MacAddressMismatchError,
    RpcCallError,
)
from aioshelly.rpc_device import RpcDevice
from aioshelly.rpc_device.models import ShellyWiFiNetwork
from aioshelly.zeroconf import async_discover_devices, async_lookup_device_by_name
from bleak.backends.device import BLEDevice
import voluptuous as vol
from zeroconf import IPVersion

from homeassistant.components import zeroconf
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_clear_address_from_match_history,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_ZEROCONF,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .ble_provisioning import (
    ProvisioningState,
    async_get_provisioning_registry,
    async_register_zeroconf_discovery,
)
from .const import (
    CONF_BLE_SCANNER_MODE,
    CONF_GEN,
    CONF_SLEEP_PERIOD,
    CONF_SSID,
    DOMAIN,
    LOGGER,
    PROVISIONING_TIMEOUT,
    BLEScannerMode,
)
from .coordinator import ShellyConfigEntry, async_reconnect_soon
from .utils import (
    get_block_device_sleep_period,
    get_coap_context,
    get_device_entry_gen,
    get_http_port,
    get_info_auth,
    get_info_gen,
    get_model_name,
    get_rpc_device_wakeup_period,
    get_ws_context,
    mac_address_from_name,
)

CONFIG_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_HTTP_PORT): vol.Coerce(int),
    }
)


BLE_SCANNER_OPTIONS = [
    BLEScannerMode.DISABLED,
    BLEScannerMode.ACTIVE,
    BLEScannerMode.PASSIVE,
]

INTERNAL_WIFI_AP_IP = "192.168.33.1"
MANUAL_ENTRY_STRING = "manual"
DISCOVERY_SOURCES = {SOURCE_BLUETOOTH, SOURCE_ZEROCONF}


# BLE provisioning flow steps that are in the finishing state
# Used to determine if a BLE flow should be aborted when zeroconf discovers the device
BLUETOOTH_FINISHING_STEPS = {"do_provision", "provision_done"}


@dataclass(frozen=True, slots=True)
class DiscoveredDeviceZeroconf:
    """Discovered Shelly device via Zeroconf."""

    name: str
    mac: str
    host: str
    port: int


@dataclass(frozen=True, slots=True)
class DiscoveredDeviceBluetooth:
    """Discovered Shelly device via Bluetooth."""

    name: str
    mac: str
    ble_device: BLEDevice
    discovery_info: BluetoothServiceInfoBleak


async def validate_input(
    hass: HomeAssistant,
    host: str,
    port: int,
    info: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from CONFIG_SCHEMA with values provided by the user.
    """
    options = ConnectionOptions(
        ip_address=host,
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        device_mac=info[CONF_MAC],
        port=port,
    )

    gen = get_info_gen(info)

    if gen in RPC_GENERATIONS:
        ws_context = await get_ws_context(hass)
        rpc_device = await RpcDevice.create(
            async_get_clientsession(hass),
            ws_context,
            options,
        )
        try:
            await rpc_device.initialize()
            sleep_period = get_rpc_device_wakeup_period(rpc_device.status)
        finally:
            await rpc_device.shutdown()

        return {
            "title": rpc_device.name,
            CONF_SLEEP_PERIOD: sleep_period,
            CONF_MODEL: (
                rpc_device.xmod_info.get("p") or rpc_device.shelly.get(CONF_MODEL)
            ),
            CONF_GEN: gen,
        }

    # Gen1
    coap_context = await get_coap_context(hass)
    block_device = await BlockDevice.create(
        async_get_clientsession(hass),
        coap_context,
        options,
    )
    try:
        await block_device.initialize()
        sleep_period = get_block_device_sleep_period(block_device.settings)
    finally:
        await block_device.shutdown()

    return {
        "title": block_device.name,
        CONF_SLEEP_PERIOD: sleep_period,
        CONF_MODEL: block_device.model,
        CONF_GEN: gen,
    }


class ShellyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shelly."""

    VERSION = 1
    MINOR_VERSION = 2

    host: str = ""
    port: int = DEFAULT_HTTP_PORT
    info: dict[str, Any] = {}
    device_info: dict[str, Any] = {}
    ble_device: BLEDevice | None = None
    device_name: str = ""
    wifi_networks: list[ShellyWiFiNetwork] = []
    selected_ssid: str = ""
    _provision_task: asyncio.Task | None = None
    _provision_result: ConfigFlowResult | None = None
    disable_ap_after_provision: bool = True
    disable_ble_rpc_after_provision: bool = True
    _discovered_devices: dict[str, DiscoveredDeviceZeroconf | DiscoveredDeviceBluetooth]
    _ble_rpc_device: RpcDevice | None = None

    @staticmethod
    def _get_name_from_mac_and_ble_model(
        mac: str, parsed_data: dict[str, int | str]
    ) -> str:
        """Generate device name from MAC and BLE manufacturer data model ID.

        For devices without a Shelly name, use model name from model ID if available.
        Gen3/4 devices advertise MAC address as name instead of "ShellyXXX-MACADDR".
        """
        if (
            (model_id := parsed_data.get("model_id"))
            and isinstance(model_id, int)
            and (model_name := get_name_from_model_id(model_id))
        ):
            # Remove spaces from model name (e.g., "Shelly 1 Mini Gen4" -> "Shelly1MiniGen4")
            return f"{model_name.replace(' ', '')}-{mac}"
        return f"Shelly-{mac}"

    def _parse_ble_device_mac_and_name(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> tuple[str | None, str]:
        """Parse MAC address and device name from BLE discovery info.

        Returns:
            Tuple of (mac, device_name) where mac is None if parsing failed.
        """
        device_name = discovery_info.name
        mac: str | None = None

        # Try to get MAC from device name first
        if mac := mac_address_from_name(device_name):
            return mac, device_name

        # Try to parse from manufacturer data
        if not (
            (parsed := parse_shelly_manufacturer_data(discovery_info.manufacturer_data))
            and (mac_with_colons := parsed.get("mac"))
            and isinstance(mac_with_colons, str)
        ):
            return None, device_name

        # Convert MAC from "CC:BA:97:C2:D6:72" to "CCBA97C2D672"
        mac = mac_with_colons.replace(":", "")
        device_name = self._get_name_from_mac_and_ble_model(mac, parsed)

        return mac, device_name

    async def _async_ensure_ble_connected(self) -> RpcDevice:
        """Ensure BLE RPC device is connected, reconnecting if needed.

        Maintains a persistent BLE connection across config flow steps to avoid
        the overhead of reconnecting between WiFi scan and provisioning steps.

        Returns:
            Connected RpcDevice instance

        Raises:
            DeviceConnectionError: If connection fails
            RpcCallError: If ping fails after connection

        """
        if TYPE_CHECKING:
            assert self.ble_device is not None

        if self._ble_rpc_device is not None and self._ble_rpc_device.connected:
            # Ping to verify connection is still alive
            try:
                await self._ble_rpc_device.update_status()
            except (DeviceConnectionError, RpcCallError):
                # Connection dropped, need to reconnect
                LOGGER.debug("BLE connection lost, reconnecting")
                await self._async_disconnect_ble()
            else:
                return self._ble_rpc_device

        # Create new connection
        LOGGER.debug("Creating new BLE RPC connection to %s", self.ble_device.address)
        options = ConnectionOptions(ble_device=self.ble_device)
        device = await RpcDevice.create(
            aiohttp_session=None, ws_context=None, ip_or_options=options
        )
        try:
            await device.initialize()
        except (DeviceConnectionError, RpcCallError):
            await device.shutdown()
            raise
        self._ble_rpc_device = device
        return self._ble_rpc_device

    async def _async_disconnect_ble(self) -> None:
        """Disconnect and cleanup BLE RPC device."""
        if self._ble_rpc_device is not None:
            try:
                await self._ble_rpc_device.shutdown()
            except Exception:  # noqa: BLE001
                LOGGER.debug("Error during BLE shutdown", exc_info=True)
            finally:
                self._ble_rpc_device = None

    async def _async_get_ip_from_ble(self) -> str | None:
        """Get device IP address via BLE after WiFi provisioning.

        Uses the persistent BLE connection to get the device's sta_ip from status.

        Returns:
            IP address string if available, None otherwise

        """
        try:
            device = await self._async_ensure_ble_connected()
        except (DeviceConnectionError, RpcCallError) as err:
            LOGGER.debug("Failed to get IP via BLE: %s", err)
            return None

        if (
            (wifi := device.status.get("wifi"))
            and isinstance(wifi, dict)
            and (ip := wifi.get("sta_ip"))
        ):
            return cast(str, ip)
        return None

    async def _async_discover_zeroconf_devices(
        self,
    ) -> dict[str, DiscoveredDeviceZeroconf]:
        """Discover Shelly devices via Zeroconf."""
        discovered: dict[str, DiscoveredDeviceZeroconf] = {}

        aiozc = await zeroconf.async_get_async_instance(self.hass)
        zeroconf_devices = await async_discover_devices(aiozc)

        for service_info in zeroconf_devices:
            device_name = service_info.name.partition(".")[0]
            if not (mac := mac_address_from_name(device_name)):
                continue

            # Get IPv4 address from service info (Shelly doesn't support IPv6)
            if not (
                ipv4_addresses := service_info.ip_addresses_by_version(IPVersion.V4Only)
            ):
                continue

            host = str(ipv4_addresses[0])
            discovered[mac] = DiscoveredDeviceZeroconf(
                name=device_name,
                mac=mac,
                host=host,
                port=service_info.port or DEFAULT_HTTP_PORT,
            )

        return discovered

    @callback
    def _async_discover_bluetooth_devices(
        self,
    ) -> dict[str, DiscoveredDeviceBluetooth]:
        """Discover Shelly devices via Bluetooth."""
        discovered: dict[str, DiscoveredDeviceBluetooth] = {}

        for discovery_info in async_discovered_service_info(self.hass, False):
            mac, device_name = self._parse_ble_device_mac_and_name(discovery_info)

            if not (
                mac
                and has_rpc_over_ble(discovery_info.manufacturer_data)
                and (
                    ble_device := async_ble_device_from_address(
                        self.hass, discovery_info.address, connectable=True
                    )
                )
            ):
                continue

            discovered[mac] = DiscoveredDeviceBluetooth(
                name=device_name,
                mac=mac,
                ble_device=ble_device,
                discovery_info=discovery_info,
            )

        return discovered

    async def _async_connect_and_get_info(
        self, host: str, port: int
    ) -> ConfigFlowResult | None:
        """Connect to device, validate, and create entry or return None to continue flow.

        This helper consolidates the common logic between Zeroconf device selection
        and manual entry flows. Returns a ConfigFlowResult if the flow should end
        (create_entry or abort), or None if the flow should continue (e.g., to credentials).

        Sets self.info, self.host, and self.port on success.
        """
        self.info = await self._async_get_info(host, port)
        await self.async_set_unique_id(self.info[CONF_MAC], raise_on_progress=False)
        self._abort_if_unique_id_configured({CONF_HOST: host})

        self.host = host
        self.port = port

        if get_info_auth(self.info):
            return None  # Continue to credentials step

        device_info = await validate_input(
            self.hass, self.host, self.port, self.info, {}
        )

        if device_info[CONF_MODEL]:
            return self.async_create_entry(
                title=device_info["title"],
                data={
                    CONF_HOST: self.host,
                    CONF_PORT: self.port,
                    CONF_SLEEP_PERIOD: device_info[CONF_SLEEP_PERIOD],
                    CONF_MODEL: device_info[CONF_MODEL],
                    CONF_GEN: device_info[CONF_GEN],
                },
            )
        return self.async_abort(reason="firmware_not_fully_provisioned")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - show discovered devices or manual entry."""
        if user_input is not None:
            selected = user_input[CONF_DEVICE]
            if selected == MANUAL_ENTRY_STRING:
                return await self.async_step_user_manual()

            # User selected a discovered device
            device_data = self._discovered_devices[selected]

            if isinstance(device_data, DiscoveredDeviceZeroconf):
                # Zeroconf device - connect directly
                try:
                    result = await self._async_connect_and_get_info(
                        device_data.host, device_data.port
                    )
                except AbortFlow:
                    raise  # Let AbortFlow propagate (e.g., already_configured)
                except DeviceConnectionError:
                    return self.async_abort(reason="cannot_connect")
                except MacAddressMismatchError:
                    return self.async_abort(reason="mac_address_mismatch")
                except CustomPortNotSupported:
                    return self.async_abort(reason="custom_port_not_supported")

                # If result is None, continue to credentials step
                if result is None:
                    return await self.async_step_credentials()
                return result

            # BLE device - start provisioning flow
            self.ble_device = device_data.ble_device
            self.device_name = device_data.name
            await self.async_set_unique_id(device_data.mac, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self.context.update(
                {
                    "title_placeholders": {"name": self.device_name},
                }
            )
            return await self.async_step_bluetooth_confirm()

        # Discover devices from both sources
        discovered_devices: dict[
            str, DiscoveredDeviceZeroconf | DiscoveredDeviceBluetooth
        ] = {}

        # Discover BLE devices first, then zeroconf (which will overwrite duplicates)
        discovered_devices.update(self._async_discover_bluetooth_devices())
        # Zeroconf devices are preferred over BLE, so update overwrites any duplicates
        discovered_devices.update(await self._async_discover_zeroconf_devices())

        # Filter out already-configured devices (excluding ignored)
        # and devices with active discovery flows (already being offered to user)
        current_ids = self._async_current_ids(include_ignore=False)
        in_progress_macs = self._async_get_in_progress_discovery_macs()
        discovered_devices = {
            mac: device
            for mac, device in discovered_devices.items()
            if mac not in current_ids and mac not in in_progress_macs
        }

        # Store discovered devices for use in selection
        self._discovered_devices = discovered_devices

        # If no devices discovered, go directly to manual entry
        if not discovered_devices:
            return await self.async_step_user_manual()

        # Build selection options for discovered devices
        device_options: list[SelectOptionDict] = [
            SelectOptionDict(label=data.name, value=mac)
            for mac, data in discovered_devices.items()
        ]
        # Add manual entry option with translation key
        device_options.append(
            SelectOptionDict(label="manual", value=MANUAL_ENTRY_STRING)
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): SelectSelector(
                        SelectSelectorConfig(
                            options=device_options,
                            translation_key=CONF_DEVICE,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_user_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual entry step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                result = await self._async_connect_and_get_info(
                    user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except AbortFlow:
                raise  # Let AbortFlow propagate (e.g., already_configured)
            except DeviceConnectionError:
                errors["base"] = "cannot_connect"
            except InvalidHostError:
                errors["base"] = "invalid_host"
            except MacAddressMismatchError:
                errors["base"] = "mac_address_mismatch"
            except CustomPortNotSupported:
                errors["base"] = "custom_port_not_supported"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # If result is None, continue to credentials step
                if result is None:
                    return await self.async_step_credentials()
                return result

        return self.async_show_form(
            step_id="user_manual", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if get_info_gen(self.info) in RPC_GENERATIONS:
                user_input[CONF_USERNAME] = "admin"
            try:
                device_info = await validate_input(
                    self.hass, self.host, self.port, self.info, user_input
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except DeviceConnectionError:
                errors["base"] = "cannot_connect"
            except MacAddressMismatchError:
                errors["base"] = "mac_address_mismatch"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if device_info[CONF_MODEL]:
                    return self.async_create_entry(
                        title=device_info["title"],
                        data={
                            **user_input,
                            CONF_HOST: self.host,
                            CONF_PORT: self.port,
                            CONF_SLEEP_PERIOD: device_info[CONF_SLEEP_PERIOD],
                            CONF_MODEL: device_info[CONF_MODEL],
                            CONF_GEN: device_info[CONF_GEN],
                        },
                    )
                return self.async_abort(reason="firmware_not_fully_provisioned")
        else:
            user_input = {}

        if get_info_gen(self.info) in RPC_GENERATIONS:
            schema = {
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): str,
            }
        else:
            schema = {
                vol.Required(
                    CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): str,
            }

        return self.async_show_form(
            step_id="credentials", data_schema=vol.Schema(schema), errors=errors
        )

    @callback
    def _async_get_in_progress_discovery_macs(self) -> set[str]:
        """Get MAC addresses of devices with active discovery flows.

        Returns MAC addresses from bluetooth and zeroconf discovery flows
        that are already in progress, so they can be filtered from the
        user step device list (since they're already being offered).
        """
        return {
            mac
            for flow in self._async_in_progress(include_uninitialized=True)
            if flow["flow_id"] != self.flow_id
            and flow["context"].get("source") in DISCOVERY_SOURCES
            and (mac := flow["context"].get("unique_id"))
        }

    def _abort_idle_ble_flows(self, mac: str) -> None:
        """Abort idle BLE provisioning flows for this device.

        When zeroconf discovers a device, it means the device is already on WiFi.
        If there's an idle BLE flow (user hasn't started provisioning yet), abort it.
        Active provisioning flows (do_provision/provision_done) should not be aborted
        as they're waiting for zeroconf handoff.
        """
        for flow in self._async_in_progress(include_uninitialized=True):
            if (
                flow["flow_id"] != self.flow_id
                and flow["context"].get("unique_id") == mac
                and flow["context"].get("source") == "bluetooth"
                and flow.get("step_id") not in BLUETOOTH_FINISHING_STEPS
            ):
                LOGGER.debug(
                    "Aborting idle BLE flow %s for %s (device discovered via zeroconf)",
                    flow["flow_id"],
                    mac,
                )
                self.hass.config_entries.flow.async_abort(flow["flow_id"])

    async def _async_handle_zeroconf_mac_discovery(
        self, mac: str, host: str, port: int
    ) -> None:
        """Handle MAC address discovery from zeroconf.

        Registers discovery info for BLE handoff and aborts idle BLE flows.
        """
        # Register this zeroconf discovery with BLE provisioning in case
        # this device was just provisioned via BLE
        async_register_zeroconf_discovery(self.hass, mac, host, port)

        # Check for idle BLE provisioning flows and abort them since
        # device is already on WiFi (discovered via zeroconf)
        self._abort_idle_ble_flows(mac)

        await self._async_discovered_mac(mac, host)

    async def _async_discovered_mac(self, mac: str, host: str) -> None:
        """Abort and reconnect soon if the device with the mac address is already configured."""
        if (
            current_entry := await self.async_set_unique_id(mac)
        ) and current_entry.data.get(CONF_HOST) == host:
            LOGGER.debug("async_reconnect_soon: host: %s, mac: %s", host, mac)
            await async_reconnect_soon(self.hass, current_entry)
        if host == INTERNAL_WIFI_AP_IP:
            # If the device is broadcasting the internal wifi ap ip
            # we can't connect to it, so we should not update the
            # entry with the new host as it will be unreachable
            #
            # This is a workaround for a bug in the firmware 0.12 (and older?)
            # which should be removed once the firmware is fixed
            # and the old version is no longer in use
            self._abort_if_unique_id_configured()
        else:
            self._abort_if_unique_id_configured({CONF_HOST: host})

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery."""
        mac, device_name = self._parse_ble_device_mac_and_name(discovery_info)

        if not mac:
            return self.async_abort(reason="invalid_discovery_info")

        # Clear match history at the start of discovery flow.
        # This ensures that if the user never provisions the device and it
        # disappears (powers down), the discovery flow gets cleaned up,
        # and then the device comes back later, it can be rediscovered.
        # Also handles factory reset scenarios where the device may reappear
        # with different advertisement content (RPC-over-BLE re-enabled).
        async_clear_address_from_match_history(self.hass, discovery_info.address)

        # Check if RPC-over-BLE is enabled - required for WiFi provisioning
        if not has_rpc_over_ble(discovery_info.manufacturer_data):
            LOGGER.debug(
                "Device %s does not have RPC-over-BLE enabled, skipping provisioning",
                discovery_info.name,
            )
            return self.async_abort(reason="invalid_discovery_info")

        # Check if already configured - abort if device is already set up
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        # Store BLE device and name for WiFi provisioning
        self.ble_device = async_ble_device_from_address(
            self.hass, discovery_info.address, connectable=True
        )
        if not self.ble_device:
            return self.async_abort(reason="cannot_connect")

        self.device_name = device_name
        self.context.update(
            {
                "title_placeholders": {"name": device_name},
            }
        )

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth provisioning."""
        if user_input is not None:
            self.disable_ap_after_provision = user_input.get("disable_ap", True)
            self.disable_ble_rpc_after_provision = user_input.get(
                "disable_ble_rpc", True
            )
            return await self.async_step_wifi_scan()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional("disable_ap", default=True): bool,
                    vol.Optional("disable_ble_rpc", default=True): bool,
                }
            ),
            description_placeholders={
                "name": self.context["title_placeholders"]["name"]
            },
        )

    async def async_step_wifi_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Scan for WiFi networks via BLE."""
        if user_input is not None:
            self.selected_ssid = user_input[CONF_SSID]
            password = user_input[CONF_PASSWORD]
            return await self.async_step_do_provision({"password": password})

        # Scan for WiFi networks via BLE using persistent connection
        try:
            device = await self._async_ensure_ble_connected()
            self.wifi_networks = await device.wifi_scan()
        except (DeviceConnectionError, RpcCallError) as err:
            LOGGER.debug("Failed to scan WiFi networks via BLE: %s", err)
            # "Writing is not permitted" error means device rejects BLE writes
            # and BLE provisioning is disabled - user must use Shelly app
            if "not permitted" in str(err):
                await self._async_disconnect_ble()
                return self.async_abort(reason="ble_not_permitted")
            return await self.async_step_wifi_scan_failed()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception during WiFi scan")
            await self._async_disconnect_ble()
            return self.async_abort(reason="unknown")

        # Sort by RSSI (strongest signal first - higher/less negative values first)
        # and create list of SSIDs for selection
        sorted_networks = sorted(
            self.wifi_networks, key=lambda n: n["rssi"], reverse=True
        )
        ssid_options = [network["ssid"] for network in sorted_networks]

        # Pre-select SSID if returning from failed provisioning attempt
        suggested_values: dict[str, Any] = {}
        if self.selected_ssid:
            suggested_values[CONF_SSID] = self.selected_ssid

        return self.async_show_form(
            step_id="wifi_scan",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_SSID): SelectSelector(
                            SelectSelectorConfig(
                                options=ssid_options,
                                mode=SelectSelectorMode.DROPDOWN,
                                custom_value=True,
                            )
                        ),
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                suggested_values,
            ),
        )

    async def async_step_wifi_scan_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle failed WiFi scan - allow retry."""
        if user_input is not None:
            # User wants to retry - go back to wifi_scan
            return await self.async_step_wifi_scan()

        return self.async_show_form(step_id="wifi_scan_failed")

    @asynccontextmanager
    async def _async_provision_context(
        self, mac: str
    ) -> AsyncIterator[ProvisioningState]:
        """Context manager to register and cleanup provisioning state."""
        state = ProvisioningState()
        provisioning_registry = async_get_provisioning_registry(self.hass)
        normalized_mac = format_mac(mac)
        provisioning_registry[normalized_mac] = state
        try:
            yield state
        finally:
            provisioning_registry.pop(normalized_mac, None)

    async def _async_secure_device_after_provision(self, host: str, port: int) -> None:
        """Disable AP and/or BLE RPC after successful WiFi provisioning.

        Must be called via IP after device is on WiFi, not via BLE.
        """
        if (
            not self.disable_ap_after_provision
            and not self.disable_ble_rpc_after_provision
        ):
            return

        # Connect to device via IP
        options = ConnectionOptions(
            host,
            None,
            None,
            device_mac=self.unique_id,
            port=port,
        )
        device: RpcDevice | None = None
        try:
            device = await RpcDevice.create(
                async_get_clientsession(self.hass), None, options
            )
            await device.initialize()

            restart_required = False

            # Disable WiFi AP if requested
            if self.disable_ap_after_provision:
                result = await device.wifi_setconfig(ap_enable=False)
                LOGGER.debug("Disabled WiFi AP on %s", host)
                restart_required = restart_required or result.get(
                    "restart_required", False
                )

            # Disable BLE RPC if requested (keep BLE enabled for sensors/buttons)
            if self.disable_ble_rpc_after_provision:
                result = await device.ble_setconfig(enable=True, enable_rpc=False)
                LOGGER.debug("Disabled BLE RPC on %s", host)
                restart_required = restart_required or result.get(
                    "restart_required", False
                )

            # Restart device once if either operation requires it
            if restart_required:
                await device.trigger_reboot(delay_ms=1000)
        except (TimeoutError, DeviceConnectionError, RpcCallError) as err:
            LOGGER.warning(
                "Failed to secure device after provisioning at %s: %s", host, err
            )
            # Don't fail the flow - device is already on WiFi and functional
        finally:
            if device:
                await device.shutdown()

    async def _async_provision_wifi_and_wait_for_zeroconf(
        self, mac: str, password: str, state: ProvisioningState
    ) -> ConfigFlowResult | None:
        """Provision WiFi credentials via BLE and wait for zeroconf discovery.

        Returns the flow result to be stored in self._provision_result, or None if failed.
        """
        # Provision WiFi via BLE using persistent connection
        try:
            device = await self._async_ensure_ble_connected()
            await device.wifi_setconfig(
                sta_ssid=self.selected_ssid,
                sta_password=password,
                sta_enable=True,
            )
        except (DeviceConnectionError, RpcCallError) as err:
            LOGGER.debug("Failed to provision WiFi via BLE: %s", err)
            # BLE connection/communication failed - allow retry from network selection
            return None
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception during WiFi provisioning")
            await self._async_disconnect_ble()
            return self.async_abort(reason="unknown")

        LOGGER.debug(
            "WiFi provisioning successful for %s, waiting for zeroconf discovery",
            mac,
        )

        # Two-phase device discovery after WiFi provisioning:
        #
        # Phase 1: Wait for zeroconf discovery callback (via event)
        # - Callback only fires on NEW zeroconf advertisements
        # - If device appears on network, we get notified immediately
        # - This is the fast path for successful provisioning
        #
        # Phase 2: Active lookup on timeout (poll)
        # - Handles case where device was factory reset and has stale zeroconf data
        # - Factory reset devices don't send zeroconf goodbye, leaving stale records
        # - The timeout ensures device has enough time to connect to WiFi
        # - Active poll forces fresh lookup, ignoring stale cached data
        #
        # Why not just poll? If we polled immediately, we'd get stale data and
        # try to connect right away, causing false failures before device is ready.
        try:
            await asyncio.wait_for(state.event.wait(), timeout=PROVISIONING_TIMEOUT)
        except TimeoutError:
            LOGGER.debug("Timeout waiting for zeroconf discovery, trying active lookup")
            # No new discovery received - device may have stale zeroconf data
            # Do active lookup to force fresh resolution

            aiozc = await zeroconf.async_get_async_instance(self.hass)
            result = await async_lookup_device_by_name(aiozc, self.device_name)

            # If we still don't have a host, try BLE fallback for alternate subnets
            if not result:
                LOGGER.debug(
                    "Active lookup failed, trying to get IP address via BLE as fallback"
                )
                if ip := await self._async_get_ip_from_ble():
                    LOGGER.debug("Got IP %s from BLE, using it", ip)
                    state.host = ip
                    state.port = DEFAULT_HTTP_PORT
                else:
                    LOGGER.debug("BLE fallback also failed - provisioning unsuccessful")
                    # Store failure info and return None - provision_done will handle redirect
                    return None
            else:
                state.host, state.port = result
        else:
            LOGGER.debug(
                "Zeroconf discovery received for device after WiFi provisioning at %s",
                state.host,
            )

        # Device discovered via zeroconf - get device info and set up directly
        if TYPE_CHECKING:
            assert state.host is not None
            assert state.port is not None
        self.host = state.host
        self.port = state.port

        try:
            self.info = await self._async_get_info(self.host, self.port)
        except DeviceConnectionError as err:
            LOGGER.debug("Failed to connect to device after WiFi provisioning: %s", err)
            # Device appeared on network but can't connect - allow retry
            return None

        if get_info_auth(self.info):
            # Device requires authentication - show credentials step
            return await self.async_step_credentials()

        try:
            device_info = await validate_input(
                self.hass, self.host, self.port, self.info, {}
            )
        except DeviceConnectionError as err:
            LOGGER.debug("Failed to validate device after WiFi provisioning: %s", err)
            # Device info validation failed - allow retry
            return None

        if not device_info[CONF_MODEL]:
            return self.async_abort(reason="firmware_not_fully_provisioned")

        # Secure device after provisioning if requested (disable AP/BLE)
        await self._async_secure_device_after_provision(self.host, self.port)

        # Clear match history so device can be rediscovered if factory reset
        # This ensures that if the device is factory reset in the future
        # (re-enabling BLE provisioning), it will trigger a new discovery flow
        if TYPE_CHECKING:
            assert self.ble_device is not None
        async_clear_address_from_match_history(self.hass, self.ble_device.address)

        # User just provisioned this device - create entry directly without confirmation
        return self.async_create_entry(
            title=device_info["title"],
            data={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_SLEEP_PERIOD: device_info[CONF_SLEEP_PERIOD],
                CONF_MODEL: device_info[CONF_MODEL],
                CONF_GEN: device_info[CONF_GEN],
            },
        )

    async def _do_provision(self, password: str) -> None:
        """Provision WiFi credentials to device via BLE."""
        if TYPE_CHECKING:
            assert self.ble_device is not None

        mac = self.unique_id
        if TYPE_CHECKING:
            assert mac is not None

        try:
            async with self._async_provision_context(mac) as state:
                self._provision_result = (
                    await self._async_provision_wifi_and_wait_for_zeroconf(
                        mac, password, state
                    )
                )
        finally:
            # Always disconnect BLE after provisioning attempt completes
            # We either succeeded (and will use IP now) or failed (and user will retry)
            await self._async_disconnect_ble()

    async def async_step_do_provision(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Execute WiFi provisioning via BLE."""
        if not self._provision_task:
            if TYPE_CHECKING:
                assert user_input is not None
            password = user_input["password"]
            self._provision_task = self.hass.async_create_task(
                self._do_provision(password), eager_start=False
            )

        if not self._provision_task.done():
            return self.async_show_progress(
                step_id="do_provision",
                progress_action="provisioning",
                progress_task=self._provision_task,
            )

        self._provision_task = None
        return self.async_show_progress_done(next_step_id="provision_done")

    async def async_step_provision_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle failed provisioning - allow retry."""
        if user_input is not None:
            # User wants to retry - keep selected_ssid so it's pre-selected
            self.wifi_networks = []
            return await self.async_step_wifi_scan()

        return self.async_show_form(
            step_id="provision_failed",
            description_placeholders={"ssid": self.selected_ssid},
        )

    async def async_step_provision_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the result of the provision step."""
        result = self._provision_result
        self._provision_result = None

        # If provisioning failed, redirect to provision_failed step
        if result is None:
            return await self.async_step_provision_failed()

        return result

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        if discovery_info.ip_address.version == 6:
            return self.async_abort(reason="ipv6_not_supported")
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_HTTP_PORT
        # First try to get the mac address from the name
        # so we can avoid making another connection to the
        # device if we already have it configured
        if mac := mac_address_from_name(discovery_info.name):
            await self._async_handle_zeroconf_mac_discovery(mac, host, port)

        try:
            # Devices behind range extender doesn't generate zeroconf packets
            # so port is always the default one
            self.info = await self._async_get_info(host, port)
        except DeviceConnectionError:
            return self.async_abort(reason="cannot_connect")

        if not mac:
            # We could not get the mac address from the name
            # so need to check here since we just got the info
            mac = self.info[CONF_MAC]
            await self._async_handle_zeroconf_mac_discovery(mac, host, port)

        self.host = host
        self.context.update(
            {
                "title_placeholders": {"name": discovery_info.name.split(".")[0]},
                "configuration_url": f"http://{discovery_info.host}",
            }
        )

        if get_info_auth(self.info):
            return await self.async_step_credentials()

        try:
            self.device_info = await validate_input(
                self.hass, self.host, self.port, self.info, {}
            )
        except DeviceConnectionError:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirm."""
        errors: dict[str, str] = {}

        if not self.device_info[CONF_MODEL]:
            return self.async_abort(reason="firmware_not_fully_provisioned")
        model = get_model_name(self.info)
        if user_input is not None:
            return self.async_create_entry(
                title=self.device_info["title"],
                data={
                    CONF_HOST: self.host,
                    CONF_SLEEP_PERIOD: self.device_info[CONF_SLEEP_PERIOD],
                    CONF_MODEL: self.device_info[CONF_MODEL],
                    CONF_GEN: self.device_info[CONF_GEN],
                },
            )
        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                CONF_MODEL: model,
                CONF_HOST: self.host,
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        host = reauth_entry.data[CONF_HOST]
        port = get_http_port(reauth_entry.data)

        if user_input is not None:
            try:
                info = await self._async_get_info(host, port)
            except (DeviceConnectionError, InvalidAuthError):
                return self.async_abort(reason="reauth_unsuccessful")

            if get_device_entry_gen(reauth_entry) != 1:
                user_input[CONF_USERNAME] = "admin"
            try:
                await validate_input(self.hass, host, port, info, user_input)
            except (DeviceConnectionError, InvalidAuthError):
                return self.async_abort(reason="reauth_unsuccessful")
            except MacAddressMismatchError:
                return self.async_abort(reason="mac_address_mismatch")

            return self.async_update_reload_and_abort(
                reauth_entry, data_updates=user_input
            )

        if get_device_entry_gen(reauth_entry) in BLOCK_GENERATIONS:
            schema = {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        else:
            schema = {vol.Required(CONF_PASSWORD): str}

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors = {}
        reconfigure_entry = self._get_reconfigure_entry()
        self.host = reconfigure_entry.data[CONF_HOST]
        self.port = reconfigure_entry.data.get(CONF_PORT, DEFAULT_HTTP_PORT)

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_HTTP_PORT)
            try:
                info = await self._async_get_info(host, port)
            except DeviceConnectionError:
                errors["base"] = "cannot_connect"
            except CustomPortNotSupported:
                errors["base"] = "custom_port_not_supported"
            else:
                await self.async_set_unique_id(info[CONF_MAC])
                self._abort_if_unique_id_mismatch(reason="another_device")

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.host): str,
                    vol.Required(CONF_PORT, default=self.port): vol.Coerce(int),
                }
            ),
            description_placeholders={"device_name": reconfigure_entry.title},
            errors=errors,
        )

    async def _async_get_info(self, host: str, port: int) -> dict[str, Any]:
        """Get info from shelly device."""
        return await get_info(async_get_clientsession(self.hass), host, port=port)

    @callback
    def async_remove(self) -> None:
        """Handle flow removal - cleanup BLE connection."""
        super().async_remove()
        if self._ble_rpc_device is not None:
            # Schedule cleanup as background task since async_remove is sync
            self.hass.async_create_background_task(
                self._async_disconnect_ble(),
                name="shelly_config_flow_ble_cleanup",
            )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ShellyConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ShellyConfigEntry) -> bool:
        """Return options flow support for this handler."""
        return get_device_entry_gen(
            config_entry
        ) in RPC_GENERATIONS and not config_entry.data.get(CONF_SLEEP_PERIOD)


class OptionsFlowHandler(OptionsFlow):
    """Handle the option flow for shelly."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if (
            supports_scripts := self.config_entry.runtime_data.rpc_supports_scripts
        ) is None:
            return self.async_abort(reason="cannot_connect")
        if not supports_scripts:
            return self.async_abort(reason="no_scripts_support")
        if self.config_entry.runtime_data.rpc_zigbee_firmware:
            return self.async_abort(reason="zigbee_firmware")

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BLE_SCANNER_MODE,
                        default=self.config_entry.options.get(
                            CONF_BLE_SCANNER_MODE, BLEScannerMode.DISABLED
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=BLE_SCANNER_OPTIONS,
                            translation_key=CONF_BLE_SCANNER_MODE,
                        ),
                    ),
                }
            ),
        )
