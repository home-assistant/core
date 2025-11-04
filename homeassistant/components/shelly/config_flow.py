"""Config flow for Shelly integration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, Final

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
from bleak.backends.device import BLEDevice
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
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
from .provision_wifi import async_provision_wifi, async_scan_wifi_networks
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
from .zeroconf_helpers import async_lookup_device_by_name

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

# BLE provisioning flow steps that are in the finishing state
# Used to determine if a BLE flow should be aborted when zeroconf discovers the device
BLUETOOTH_FINISHING_STEPS = {"do_provision", "provision_done"}


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
    wifi_networks: list[dict[str, Any]] = []
    selected_ssid: str = ""
    _provision_task: asyncio.Task | None = None
    _provision_result: ConfigFlowResult | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            try:
                self.info = await self._async_get_info(host, port)
            except DeviceConnectionError:
                errors["base"] = "cannot_connect"
            except InvalidHostError:
                errors["base"] = "invalid_host"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    self.info[CONF_MAC], raise_on_progress=False
                )
                self._abort_if_unique_id_configured({CONF_HOST: host})
                self.host = host
                self.port = port
                if get_info_auth(self.info):
                    return await self.async_step_credentials()

                try:
                    device_info = await validate_input(
                        self.hass, host, port, self.info, {}
                    )
                except DeviceConnectionError:
                    errors["base"] = "cannot_connect"
                except MacAddressMismatchError:
                    errors["base"] = "mac_address_mismatch"
                except CustomPortNotSupported:
                    errors["base"] = "custom_port_not_supported"
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    if device_info[CONF_MODEL]:
                        return self.async_create_entry(
                            title=device_info["title"],
                            data={
                                CONF_HOST: user_input[CONF_HOST],
                                CONF_PORT: user_input[CONF_PORT],
                                CONF_SLEEP_PERIOD: device_info[CONF_SLEEP_PERIOD],
                                CONF_MODEL: device_info[CONF_MODEL],
                                CONF_GEN: device_info[CONF_GEN],
                            },
                        )
                    return self.async_abort(reason="firmware_not_fully_provisioned")

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
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

    def _abort_idle_ble_flows(self, mac: str) -> None:
        """Abort idle BLE provisioning flows for this device.

        When zeroconf discovers a device, it means the device is already on WiFi.
        If there's an idle BLE flow (user hasn't started provisioning yet), abort it.
        Active provisioning flows (do_provision/provision_done) should not be aborted
        as they're waiting for zeroconf handoff.
        """
        normalized_mac = format_mac(mac)

        for flow in self._async_in_progress(include_uninitialized=True):
            if (
                flow["flow_id"] != self.flow_id
                and flow["context"].get("unique_id") == normalized_mac
                and flow["context"].get("source") == "bluetooth"
                and flow.get("step_id") not in BLUETOOTH_FINISHING_STEPS
            ):
                LOGGER.debug(
                    "Aborting idle BLE flow %s for %s (device discovered via zeroconf)",
                    flow["flow_id"],
                    normalized_mac,
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
        # Parse MAC address from the Bluetooth device name
        if not (mac := mac_address_from_name(discovery_info.name)):
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

        self.device_name = discovery_info.name
        self.context.update(
            {
                "title_placeholders": {"name": discovery_info.name},
            }
        )

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth provisioning."""
        if user_input is not None:
            return await self.async_step_wifi_scan()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self.context["title_placeholders"]["name"]
            },
        )

    async def async_step_wifi_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Scan for WiFi networks via BLE."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.selected_ssid = user_input[CONF_SSID]
            return await self.async_step_wifi_credentials()

        # Scan for WiFi networks via BLE
        assert self.ble_device is not None
        try:
            self.wifi_networks = await async_scan_wifi_networks(self.ble_device)
        except (DeviceConnectionError, RpcCallError) as err:
            LOGGER.debug("Failed to scan WiFi networks via BLE: %s", err)
            # "Writing is not permitted" error means device is bound to Shelly cloud
            # and BLE provisioning is disabled - user must use Shelly app
            if "Writing is not permitted" in str(err):
                return self.async_abort(reason="ble_not_permitted")
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception during WiFi scan")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="wifi_scan",
                errors=errors,
            )

        # Create list of SSIDs for selection
        # If no networks found, still allow custom SSID entry
        ssid_options = [network["ssid"] for network in self.wifi_networks]

        return self.async_show_form(
            step_id="wifi_scan",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SSID): SelectSelector(
                        SelectSelectorConfig(
                            options=ssid_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )

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

    async def async_step_wifi_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Get WiFi credentials and provision device."""
        if user_input is not None:
            self.selected_ssid = user_input.get(CONF_SSID, self.selected_ssid)
            password = user_input[CONF_PASSWORD]
            return await self.async_step_do_provision({"password": password})

        return self.async_show_form(
            step_id="wifi_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"ssid": self.selected_ssid},
        )

    async def _async_provision_wifi_and_wait_for_zeroconf(
        self, mac: str, password: str, state: ProvisioningState
    ) -> ConfigFlowResult:
        """Provision WiFi credentials via BLE and wait for zeroconf discovery.

        Returns the flow result to be stored in self._provision_result.
        """
        # Provision WiFi via BLE
        assert self.ble_device is not None
        try:
            await async_provision_wifi(self.ble_device, self.selected_ssid, password)
        except (DeviceConnectionError, RpcCallError):
            return self.async_show_form(
                step_id="wifi_credentials",
                data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
                description_placeholders={"ssid": self.selected_ssid},
                errors={"base": "cannot_connect"},
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception during WiFi provisioning")
            return self.async_abort(reason="unknown")

        LOGGER.debug(
            "WiFi provisioning successful for %s, waiting for zeroconf discovery",
            mac,
        )

        # Abort any other flows for this device
        for flow in self._async_in_progress(include_uninitialized=True):
            flow_unique_id = flow["context"].get("unique_id")
            if flow["flow_id"] != self.flow_id and self.unique_id == flow_unique_id:
                self.hass.config_entries.flow.async_abort(flow["flow_id"])

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
            LOGGER.debug(
                "Zeroconf discovered device after WiFi provisioning at %s",
                state.host,
            )
        except TimeoutError:
            LOGGER.debug("Timeout waiting for zeroconf discovery, trying active lookup")
            # No new discovery received - device may have stale zeroconf data
            # Do active lookup to force fresh resolution

            aiozc = await zeroconf.async_get_async_instance(self.hass)
            result = await async_lookup_device_by_name(aiozc, self.device_name)

            # If we still don't have a host, provisioning failed
            if not result:
                LOGGER.debug("Active lookup failed - provisioning unsuccessful")
                return self.async_show_form(
                    step_id="provision_failed",
                    description_placeholders={"ssid": self.selected_ssid},
                )

            state.host, state.port = result

        # Device discovered via zeroconf - get device info and set up directly
        assert state.host is not None
        assert state.port is not None
        self.host = state.host
        self.port = state.port

        try:
            self.info = await self._async_get_info(self.host, self.port)
        except DeviceConnectionError:
            return self.async_abort(reason="cannot_connect")

        if get_info_auth(self.info):
            # Device requires authentication - show credentials step
            return await self.async_step_credentials()

        try:
            device_info = await validate_input(
                self.hass, self.host, self.port, self.info, {}
            )
        except DeviceConnectionError:
            return self.async_abort(reason="cannot_connect")

        if not device_info[CONF_MODEL]:
            return self.async_abort(reason="firmware_not_fully_provisioned")

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
        assert self.ble_device is not None

        mac = self.unique_id
        assert mac is not None

        async with self._async_provision_context(mac) as state:
            self._provision_result = (
                await self._async_provision_wifi_and_wait_for_zeroconf(
                    mac, password, state
                )
            )

    async def async_step_do_provision(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Execute WiFi provisioning via BLE."""
        if not self._provision_task:
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
            # User wants to retry - go back to wifi_scan
            return await self.async_step_wifi_scan()

        return self.async_show_form(
            step_id="provision_failed",
            description_placeholders={"ssid": self.selected_ssid},
        )

    async def async_step_provision_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the result of the provision step."""
        assert self._provision_result is not None
        result = self._provision_result
        self._provision_result = None
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
