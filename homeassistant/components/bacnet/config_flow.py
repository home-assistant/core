"""Config flow for the BACnet integration."""

from __future__ import annotations

from asyncio import timeout
import ipaddress
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers import config_validation as cv

from .bacnet_client import BACnetDeviceInfo, get_local_interfaces
from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_ENTRY_TYPE,
    CONF_HUB_ID,
    CONF_INTERFACE,
    CONF_SELECTED_OBJECTS,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    ENTRY_TYPE_DEVICE,
    ENTRY_TYPE_HUB,
)

_LOGGER = logging.getLogger(__name__)


class BACnetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BACnet."""

    VERSION = 2  # Increment version for hub model

    _discovered_devices: list[BACnetDeviceInfo] = []
    _discovered_objects: list = []
    _selected_address: str | None = None
    _selected_device: BACnetDeviceInfo | None = None
    _hub_entry_id: str | None = None

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> BACnetOptionsFlow:
        """Get the options flow for this handler."""
        return BACnetOptionsFlow(config_entry)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the config flow."""
        super().__init__(*args, **kwargs)
        self._discovered_devices = []
        self._discovered_objects = []
        self._selected_address = None
        self._selected_device = None
        self._hub_entry_id = None

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        device_id = discovery_info[CONF_DEVICE_ID]
        device_address = discovery_info[CONF_DEVICE_ADDRESS]
        hub_id = discovery_info[CONF_HUB_ID]
        name = discovery_info.get("name", f"BACnet device {device_id}")
        vendor = discovery_info.get("vendor_name", "")
        model = discovery_info.get("model_name", "")

        # Set unique ID to prevent duplicates
        await self.async_set_unique_id(str(device_id))
        self._abort_if_unique_id_configured()

        # Build description
        description = name
        if vendor and model:
            description += f" ({vendor} - {model})"
        elif vendor:
            description += f" ({vendor})"
        elif model:
            description += f" ({model})"
        description += f" at {device_address}"

        # Store discovery data
        self._selected_device = BACnetDeviceInfo(
            device_id=device_id,
            address=device_address,
            name=name,
            vendor_name=vendor,
            model_name=model,
        )
        self._hub_entry_id = hub_id

        # Show confirmation form
        return self.async_show_form(
            step_id="integration_discovery_confirm",
            description_placeholders={"device_name": description},
        )

    async def async_step_integration_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is None:
            # Build device description for the confirmation dialog
            if self._selected_device:
                name = (
                    self._selected_device.name
                    or f"Device {self._selected_device.device_id}"
                )
                if (
                    self._selected_device.vendor_name
                    and self._selected_device.model_name
                ):
                    description = f"{name} ({self._selected_device.vendor_name} - {self._selected_device.model_name})"
                elif self._selected_device.vendor_name:
                    description = f"{name} ({self._selected_device.vendor_name})"
                elif self._selected_device.model_name:
                    description = f"{name} ({self._selected_device.model_name})"
                else:
                    description = name
                description += f" at {self._selected_device.address}"
            else:
                description = "Unknown device"

            return self.async_show_form(
                step_id="integration_discovery_confirm",
                description_placeholders={"device_name": description},
            )

        # Create entry directly - object discovery will happen during setup
        # Creating entry without object selection uses all objects by default
        if not self._selected_device or not self._hub_entry_id:
            return self.async_abort(reason="device_not_selected")

        title = (
            self._selected_device.name
            or f"BACnet device {self._selected_device.device_id}"
        )

        return self.async_create_entry(
            title=title,
            data={
                CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
                CONF_DEVICE_ID: self._selected_device.device_id,
                CONF_DEVICE_ADDRESS: self._selected_device.address,
                CONF_HUB_ID: self._hub_entry_id,
            },
            options={
                CONF_SELECTED_OBJECTS: [],  # Empty list means all objects
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - add BACnet hub."""
        errors: dict[str, str] = {}

        # Check if hub already exists
        existing_hubs = [
            entry
            for entry in self._async_current_entries()
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB
        ]
        if existing_hubs:
            # Hub already exists, redirect to add device
            return await self.async_step_add_device_select_hub(user_input)

        if user_input is not None:
            selected = user_input[CONF_INTERFACE]

            # Handle manual entry
            if selected == "manual":
                return await self.async_step_manual_interface()

            self._selected_address = selected
            return await self.async_step_create_hub()

        # Get available network interfaces
        try:
            interfaces = await get_local_interfaces()
            if not interfaces:
                errors["base"] = "no_interfaces"
        except Exception:
            _LOGGER.exception("Failed to get network interfaces")
            errors["base"] = "unknown"
            interfaces = {}

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        # Find the best default address (prefer specific address over 0.0.0.0 and manual)
        default_address = "0.0.0.0"
        for ip, desc in interfaces.items():
            if ip not in ("0.0.0.0", "manual"):
                default_address = ip
                break  # Use the first real address

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

    async def async_step_manual_interface(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP address entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            ip_address = user_input[CONF_INTERFACE].strip()

            # Validate IP address format
            if ip_address and ip_address != "0.0.0.0":
                try:
                    ipaddress.IPv4Address(ip_address)
                    self._selected_address = ip_address
                    return await self.async_step_create_hub()
                except ValueError:
                    errors["base"] = "invalid_ip"
            elif ip_address == "0.0.0.0":
                self._selected_address = ip_address
                return await self.async_step_create_hub()
            else:
                errors["base"] = "invalid_ip"

        return self.async_show_form(
            step_id="manual_interface",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INTERFACE): str,
                }
            ),
            errors=errors,
        )

    async def async_step_create_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the BACnet hub entry."""
        # Create hub config entry
        return self.async_create_entry(
            title=f"BACnet Client ({self._selected_address})",
            data={
                CONF_ENTRY_TYPE: ENTRY_TYPE_HUB,
                CONF_INTERFACE: self._selected_address,
            },
        )

    async def async_step_add_device_select_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select which hub to add device to (in case there are multiple hubs in future)."""
        # For now, just get the first (and only) hub
        hub_entries = [
            entry
            for entry in self._async_current_entries()
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB
        ]

        if not hub_entries:
            return self.async_abort(reason="no_hub")

        # Use the first hub
        self._hub_entry_id = hub_entries[0].entry_id
        return await self.async_step_discover()

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Discover BACnet devices on the network."""
        errors: dict[str, str] = {}

        if user_input is not None and CONF_DEVICE_ID in user_input:
            # User selected a device from the discovered list
            device_id = int(user_input[CONF_DEVICE_ID])
            selected_device: BACnetDeviceInfo | None = None
            for device in self._discovered_devices:
                if device.device_id == device_id:
                    selected_device = device
                    break

            if selected_device is None:
                errors["base"] = "device_not_found"
            else:
                await self.async_set_unique_id(str(selected_device.device_id))
                self._abort_if_unique_id_configured()

                # Store the selected device and proceed to object discovery
                self._selected_device = selected_device
                # End current progress before starting new one
                self.async_show_progress_done(next_step_id="discover_objects")
                return await self.async_step_discover_objects()

        # If we got here with user_input but no device_id, user clicked retry after error

        # Get hub entry to access the client
        if not self._hub_entry_id:
            return self.async_abort(reason="no_hub")

        hub_entry = self.hass.config_entries.async_get_entry(self._hub_entry_id)
        if (
            not hub_entry
            or not hasattr(hub_entry, "runtime_data")
            or not hub_entry.runtime_data
        ):
            return self.async_abort(reason="hub_not_ready")

        client = hub_entry.runtime_data.client

        # Check if this is the first call (start discovery) or second call (handle results)
        if not self._discovered_devices and not hasattr(
            self, "_device_discovery_errors"
        ):
            # First call - start discovery with progress
            self._device_discovery_errors: dict[str, str] = {}

            async def _discover_task():
                try:
                    async with timeout(DISCOVERY_TIMEOUT + 5):
                        self._discovered_devices = await client.discover_devices(
                            timeout=DISCOVERY_TIMEOUT
                        )
                except TimeoutError:
                    _LOGGER.error("Discovery timeout")
                    self._device_discovery_errors["base"] = "discovery_timeout"
                    self._discovered_devices = []
                except Exception:
                    _LOGGER.exception("Error during BACnet discovery")
                    self._device_discovery_errors["base"] = "cannot_connect"
                    self._discovered_devices = []

            # Return progress immediately so UI renders
            return self.async_show_progress(
                step_id="discover",
                progress_action="discovering_devices",
                progress_task=self.hass.async_create_task(_discover_task()),
            )

        # Second call - discovery completed, handle results
        errors = self._device_discovery_errors
        delattr(self, "_device_discovery_errors")  # Clean up

        if not self._discovered_devices and not errors:
            errors["base"] = "no_devices_found"

        if errors:
            self.async_show_progress_done(next_step_id="discover")
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        # Build the selection options
        device_options: dict[str, str] = {}
        try:
            for device in self._discovered_devices:
                label = device.name or f"Device {device.device_id}"
                if device.vendor_name and device.model_name:
                    label += f" ({device.vendor_name} - {device.model_name})"
                elif device.vendor_name:
                    label += f" ({device.vendor_name})"
                elif device.model_name:
                    label += f" ({device.model_name})"
                label += f" [{device.address}]"
                device_options[str(device.device_id)] = label
        except Exception:
            _LOGGER.exception("Error building device options")
            self.async_show_progress_done(next_step_id="discover")
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({}),
                errors={"base": "unknown"},
            )

        self.async_show_progress_done(next_step_id="discover")
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): vol.In(device_options),
                }
            ),
            errors=errors,
        )

    async def async_step_discover_objects(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Discover objects from the selected device."""
        if not self._selected_device or not self._hub_entry_id:
            return self.async_abort(reason="device_not_selected")

        # Get client from hub
        hub_entry = self.hass.config_entries.async_get_entry(self._hub_entry_id)
        if (
            not hub_entry
            or not hasattr(hub_entry, "runtime_data")
            or not hub_entry.runtime_data
        ):
            return self.async_abort(reason="hub_not_ready")

        client = hub_entry.runtime_data.client

        # Check if this is the first call (start discovery) or second call (handle results)
        if not self._discovered_objects and not hasattr(
            self, "_objects_discovery_errors"
        ):
            # First call - start discovery with progress
            self._objects_discovery_errors: dict[str, str] = {}

            async def _discover_objects_task():
                try:
                    async with timeout(30):  # Give more time for object discovery
                        self._discovered_objects = await client.get_device_objects(
                            self._selected_device.address,
                            self._selected_device.device_id,
                        )
                except TimeoutError:
                    _LOGGER.error("Timeout discovering objects")
                    self._objects_discovery_errors["base"] = "discovery_timeout"
                except Exception:
                    _LOGGER.exception("Error discovering objects")
                    self._objects_discovery_errors["base"] = "cannot_connect"

            # Return progress immediately so UI renders
            return self.async_show_progress(
                step_id="discover_objects",
                progress_action="discovering_objects",
                progress_task=self.hass.async_create_task(_discover_objects_task()),
            )

        # Second call - discovery completed, handle results
        errors = self._objects_discovery_errors
        delattr(self, "_objects_discovery_errors")  # Clean up

        if errors:
            self.async_show_progress_done(next_step_id="sensors")
            return self.async_show_form(
                step_id="sensors",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        self.async_show_progress_done(next_step_id="sensors")

        if not self._discovered_objects:
            # No objects found, create entry with empty selection
            title = (
                self._selected_device.name
                or f"BACnet device {self._selected_device.device_id}"
            )
            return self.async_create_entry(
                title=title,
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
                    CONF_DEVICE_ID: self._selected_device.device_id,
                    CONF_DEVICE_ADDRESS: self._selected_device.address,
                    CONF_HUB_ID: self._hub_entry_id,
                },
                options={
                    CONF_SELECTED_OBJECTS: [],
                },
            )

        # If there are too many objects (>100), skip selection and add all
        if len(self._discovered_objects) > 100:
            title = (
                self._selected_device.name
                or f"BACnet device {self._selected_device.device_id}"
            )
            # Select all objects by default
            all_objects = [
                f"{obj.object_type},{obj.object_instance}"
                for obj in self._discovered_objects
            ]
            return self.async_create_entry(
                title=title,
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
                    CONF_DEVICE_ID: self._selected_device.device_id,
                    CONF_DEVICE_ADDRESS: self._selected_device.address,
                    CONF_HUB_ID: self._hub_entry_id,
                },
                options={
                    CONF_SELECTED_OBJECTS: all_objects,
                },
            )

        # Proceed to sensor selection (objects already discovered and stored in self._discovered_objects)
        return await self.async_step_sensors()

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let user select which sensors to add."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User has selected sensors, create the entry
            selected_objects = user_input.get(CONF_SELECTED_OBJECTS, [])

            if not self._selected_device or not self._hub_entry_id:
                return self.async_abort(reason="device_not_selected")

            title = (
                self._selected_device.name
                or f"BACnet device {self._selected_device.device_id}"
            )

            return self.async_create_entry(
                title=title,
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
                    CONF_DEVICE_ID: self._selected_device.device_id,
                    CONF_DEVICE_ADDRESS: self._selected_device.address,
                    CONF_HUB_ID: self._hub_entry_id,
                },
                options={
                    CONF_SELECTED_OBJECTS: selected_objects,
                },
            )

        # Use pre-discovered objects from async_step_discover_objects
        if not self._selected_device or not self._hub_entry_id:
            return self.async_abort(reason="device_not_selected")

        # Build object selection options
        object_options = {}
        for obj in self._discovered_objects:
            obj_key = f"{obj.object_type},{obj.object_instance}"
            label = obj.object_name or f"{obj.object_type} {obj.object_instance}"
            if obj.units:
                label += f" ({obj.units})"
            object_options[obj_key] = label

        # Default to selecting all objects
        default_selection = list(object_options.keys())

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SELECTED_OBJECTS, default=default_selection
                    ): cv.multi_select(object_options),
                }
            ),
            errors=errors,
            description_placeholders={
                "device_name": self._selected_device.name
                or f"Device {self._selected_device.device_id}",
                "object_count": str(len(self._discovered_objects)),
            },
        )


class BACnetOptionsFlow(OptionsFlow):
    """Handle options flow for BACnet integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the BACnet options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Update options with new sensor selection
            return self.async_create_entry(
                title="",
                data={
                    CONF_SELECTED_OBJECTS: user_input.get(CONF_SELECTED_OBJECTS, []),
                },
            )

        # Get coordinator data to show available objects
        if (
            not hasattr(self.config_entry, "runtime_data")
            or not self.config_entry.runtime_data
        ):
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors={"base": "hub_not_ready"},
            )

        runtime_data = self.config_entry.runtime_data
        coordinator = runtime_data.coordinator

        if coordinator.data is None or not coordinator.data.objects:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors={"base": "no_objects"},
                description_placeholders={"error": "No objects discovered yet"},
            )

        # Build object selection options
        object_options = {}
        for obj in coordinator.data.objects:
            obj_key = f"{obj.object_type},{obj.object_instance}"
            label = obj.object_name or f"{obj.object_type} {obj.object_instance}"
            if obj.units:
                label += f" ({obj.units})"
            object_options[obj_key] = label

        # Get current selection from options
        current_selection = self.config_entry.options.get(CONF_SELECTED_OBJECTS, [])

        # If no current selection, default to all objects
        if not current_selection:
            current_selection = list(object_options.keys())

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SELECTED_OBJECTS, default=current_selection
                    ): cv.multi_select(object_options),
                }
            ),
            errors=errors,
            description_placeholders={
                "device_name": coordinator.device_info.name
                or f"Device {coordinator.device_info.device_id}",
                "object_count": str(len(coordinator.data.objects)),
            },
        )
