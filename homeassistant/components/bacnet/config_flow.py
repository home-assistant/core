"""Config flow for the BACnet integration."""

from __future__ import annotations

import hashlib
import ipaddress
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback

from .bacnet_client import get_local_interfaces
from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DEVICE_INSTANCE,
    CONF_DEVICES,
    CONF_INTERFACE,
    CONF_SELECTED_OBJECTS,
    DEFAULT_PORT,
    DEVICE_INSTANCE_MAX,
    DEVICE_INSTANCE_MIN,
    DOMAIN,
)

MANUAL_ENTRY = "manual"


def _validate_ip(ip_str: str) -> str | None:
    """Validate an IP address string. Return error key or None if valid."""
    if not ip_str:
        return "invalid_ip"
    try:
        addr = ipaddress.IPv4Address(ip_str)
    except ValueError:
        return "invalid_ip"
    if addr.is_unspecified:
        return "invalid_ip"
    return None


class BACnetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BACnet."""

    VERSION = 3

    _selected_address: str | None = None
    _interfaces: dict[str, str] | None = None
    _discovery_info: dict[str, Any] | None = None

    def _interface_already_used(
        self, interface: str, exclude_entry_id: str | None = None
    ) -> bool:
        """Check if an interface is already used by another BACnet hub."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id == exclude_entry_id:
                continue
            if entry.data.get(CONF_INTERFACE) == interface:
                return True
        return False

    async def _async_get_interfaces(self, errors: dict[str, str]) -> dict[str, str]:
        """Fetch local interfaces, populating errors on failure."""
        try:
            interfaces = await get_local_interfaces()
            if not interfaces:
                errors["base"] = "no_interfaces"
        except Exception:  # noqa: BLE001
            errors["base"] = "unknown"
            interfaces = {}
        return interfaces

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {"device": AddDeviceSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - add a BACnet client hub."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input[CONF_INTERFACE]

            self._async_abort_entries_match({CONF_INTERFACE: selected})

            # Generate a deterministic device instance from HA UUID + interface
            # so the BACnet client has a unique identity on the network
            ha_uuid = self.hass.data.get("core.uuid", "")
            seed = f"{ha_uuid}-{selected}"
            hash_int = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
            instance_range = DEVICE_INSTANCE_MAX - DEVICE_INSTANCE_MIN + 1
            device_instance = DEVICE_INSTANCE_MIN + (hash_int % instance_range)

            # Use stored interface label for the entry title
            label = (self._interfaces or {}).get(selected, selected)
            return self.async_create_entry(
                title=f"BACnet Client ({label})",
                data={
                    CONF_INTERFACE: selected,
                    CONF_DEVICE_INSTANCE: device_instance,
                    CONF_DEVICES: {},
                },
            )

        # Get available network interfaces (always needed to re-show form)
        interfaces = await self._async_get_interfaces(errors)

        if errors and not interfaces:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        # Only show real interfaces (no manual entry option)
        interfaces = {k: v for k, v in interfaces.items() if k != "manual"}
        self._interfaces = interfaces

        # Default to the first interface
        default_address = next(iter(interfaces), None)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INTERFACE, default=default_address): vol.In(
                        interfaces
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of a BACnet hub entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input[CONF_INTERFACE]

            # Handle manual entry
            if selected == "manual":
                return await self.async_step_reconfigure_manual()

            if self._interface_already_used(
                selected, exclude_entry_id=reconfigure_entry.entry_id
            ):
                errors["base"] = "already_in_use"
            else:
                label = (self._interfaces or {}).get(selected, selected)
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=f"BACnet Client ({label})",
                    data_updates={CONF_INTERFACE: selected},
                )

        # Get available network interfaces (always needed to re-show form)
        interfaces = await self._async_get_interfaces(errors)

        if errors and not interfaces:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        self._interfaces = interfaces

        # Default to the currently configured interface
        current_interface = reconfigure_entry.data.get(CONF_INTERFACE, "")
        default_address = (
            current_interface
            if current_interface in interfaces
            else next((ip for ip in interfaces if ip != "manual"), None)
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INTERFACE, default=default_address): vol.In(
                        interfaces
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP address entry during reconfiguration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            ip_addr = user_input[CONF_INTERFACE].strip()

            error = _validate_ip(ip_addr)
            if error:
                errors["base"] = error
            elif self._interface_already_used(
                ip_addr, exclude_entry_id=reconfigure_entry.entry_id
            ):
                errors["base"] = "already_in_use"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_INTERFACE: ip_addr},
                )

        return self.async_show_form(
            step_id="reconfigure_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INTERFACE): str,
                }
            ),
            errors=errors,
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a discovered BACnet device."""
        device_id: int = discovery_info[CONF_DEVICE_ID]

        # Check if device is already configured in any hub
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            for dc in entry.data.get(CONF_DEVICES, {}).values():
                if dc.get(CONF_DEVICE_ID) == device_id:
                    return self.async_abort(reason="already_configured")

        # Deduplicate discovery flows and respect ignored entries
        await self.async_set_unique_id(f"bacnet_device_{device_id}")
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["hub_entry_id"] = discovery_info["hub_entry_id"]  # type: ignore[typeddict-unknown-key]
        device_name = discovery_info.get("device_name", f"Device {device_id}")
        address = discovery_info.get(CONF_DEVICE_ADDRESS, "")
        vendor = discovery_info.get("vendor_name", "")
        model = discovery_info.get("model_name", "")
        self.context["title_placeholders"] = {
            "name": device_name,
            "address": address,
            "vendor": vendor,
            "model": model,
        }

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm addition of a discovered BACnet device."""
        assert self._discovery_info is not None

        if user_input is not None:
            hub_entry_id = self._discovery_info["hub_entry_id"]
            hub_entry = self.hass.config_entries.async_get_entry(hub_entry_id)

            if hub_entry is None:
                return self.async_abort(reason="hub_not_ready")

            device_id = self._discovery_info[CONF_DEVICE_ID]
            device_address = self._discovery_info[CONF_DEVICE_ADDRESS]

            # Re-check in case device was added while flow was pending
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                for dc in entry.data.get(CONF_DEVICES, {}).values():
                    if dc.get(CONF_DEVICE_ID) == device_id:
                        return self.async_abort(reason="already_configured")

            devices = dict(hub_entry.data.get(CONF_DEVICES, {}))
            devices[str(device_id)] = {
                CONF_DEVICE_ID: device_id,
                CONF_DEVICE_ADDRESS: device_address,
                CONF_SELECTED_OBJECTS: [],
            }
            self.hass.config_entries.async_update_entry(
                hub_entry,
                data={**hub_entry.data, CONF_DEVICES: devices},
            )

            return self.async_abort(reason="device_added")

        device_name = self._discovery_info.get(
            "device_name", f"Device {self._discovery_info[CONF_DEVICE_ID]}"
        )
        address = self._discovery_info.get(CONF_DEVICE_ADDRESS, "")
        vendor = self._discovery_info.get("vendor_name", "")
        model = self._discovery_info.get("model_name", "")
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": device_name,
                "address": address,
                "vendor": vendor,
                "model": model,
            },
        )


@callback
def _abort_discovery_flow_for_device(hass: HomeAssistant, device_id: int) -> None:
    """Abort any pending discovery flow for a specific device ID."""
    unique_id = f"bacnet_device_{device_id}"
    for flow in hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, match_context={"source": "discovery"}
    ):
        if flow["context"].get("unique_id") == unique_id:
            hass.config_entries.flow.async_abort(flow["flow_id"])


@callback
def async_abort_discovery_flows_for_hub(hass: HomeAssistant, hub_entry_id: str) -> None:
    """Abort all pending discovery flows originating from a hub entry."""
    for flow in hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, match_context={"source": "discovery", "hub_entry_id": hub_entry_id}
    ):
        hass.config_entries.flow.async_abort(flow["flow_id"])


class AddDeviceSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a BACnet device via subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Go straight to manual device entry."""
        entry = self._get_entry()

        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="hub_not_ready")

        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle adding a BACnet device by IP address."""
        entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            ip_address = user_input[CONF_DEVICE_ADDRESS].strip()
            port = user_input.get("port", DEFAULT_PORT)

            # Validate IP
            error = _validate_ip(ip_address)
            if error:
                errors[CONF_DEVICE_ADDRESS] = error

            if not errors:
                # Build address string for directed discovery
                address = ip_address if port == DEFAULT_PORT else f"{ip_address}:{port}"

                # Try directed WhoIs to discover device at this address
                client = entry.runtime_data.client
                device_info = None
                try:
                    device_info = await client.discover_device_at_address(
                        address, timeout=5
                    )
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_connect"

                if not errors and device_info is None:
                    errors["base"] = "device_not_found_at_address"

                if not errors and device_info is not None:
                    device_id = device_info.device_id

                    # Check if device is already configured in any hub
                    for hub_entry in self.hass.config_entries.async_entries(DOMAIN):
                        devices = hub_entry.data.get(CONF_DEVICES, {})
                        for device_config in devices.values():
                            if device_config.get(CONF_DEVICE_ID) == device_id:
                                return self.async_abort(reason="already_configured")

                    # Add device to hub entry data
                    devices = dict(entry.data.get(CONF_DEVICES, {}))
                    devices[str(device_id)] = {
                        CONF_DEVICE_ID: device_id,
                        CONF_DEVICE_ADDRESS: device_info.address,
                        CONF_SELECTED_OBJECTS: [],
                    }
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_DEVICES: devices},
                    )

                    # Abort any pending discovery flow for this device
                    _abort_discovery_flow_for_device(self.hass, device_id)

                    return self.async_abort(reason="device_added")

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ADDRESS): str,
                    vol.Optional("port", default=DEFAULT_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"hub_name": entry.title},
        )
