"""Config flow for Grandstream Home."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from grandstream_home_api import (
    attempt_login,
    create_api_instance,
    detect_device_type,
    determine_device_type_from_product,
    encrypt_password,
    extract_mac_from_name,
    extract_port_from_txt,
    generate_unique_id,
    get_default_port,
    get_default_username,
    get_device_info_from_txt,
    get_device_model_from_product,
    is_grandstream_device,
    validate_ip_address,
    validate_port,
)
from grandstream_home_api.error import GrandstreamError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_DEVICE_MODEL,
    CONF_DEVICE_TYPE,
    CONF_FIRMWARE_VERSION,
    CONF_PASSWORD,
    CONF_PRODUCT_MODEL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_HTTPS_PORT,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEFAULT_USERNAME_GNS,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GrandstreamConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grandstream Home."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._port: int = DEFAULT_PORT
        self._device_type: str | None = None
        self._device_model: str | None = None  # Original device model (GDS/GSC/GNS)
        self._product_model: str | None = (
            None  # Specific product model (e.g., GDS3725, GDS3727, GSC3560)
        )
        self._auth_info: dict[str, Any] | None = None
        self._mac: str | None = None  # MAC address from discovery
        self._firmware_version: str | None = None  # Firmware version from discovery

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step for manual addition.

        Args:
            user_input: User input data from the form

        Returns:
            FlowResult: Next step or form to show

        """
        errors = {}

        if user_input is not None:
            # Validate IP address
            if not validate_ip_address(user_input[CONF_HOST]):
                errors["host"] = "invalid_host"

            if not errors:
                self._host = user_input[CONF_HOST].strip()
                self._name = user_input[CONF_NAME].strip()

                # Auto-detect device type
                detected_type = await self.hass.async_add_executor_job(
                    detect_device_type, self._host
                )

                if detected_type is None:
                    # Could not detect, default to GDS
                    _LOGGER.warning(
                        "Could not auto-detect device type for %s, defaulting to GDS",
                        self._host,
                    )
                    detected_type = DEVICE_TYPE_GDS

                self._device_type = detected_type
                self._device_model = detected_type
                self._port = get_default_port(detected_type)

                _LOGGER.info(
                    "Manual device addition: %s (Auto-detected type: %s)",
                    self._name,
                    self._device_type,
                )

                return await self.async_step_auth()

        # Show form with input fields (removed device type selection)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_NAME): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle zeroconf discovery callback."""
        self._host = discovery_info.host
        txt_properties = discovery_info.properties or {}

        _LOGGER.info(
            "Zeroconf discovery received - Type: %s, Host: %s, Port: %s, Name: %s",
            discovery_info.type,
            self._host,
            discovery_info.port,
            discovery_info.name,
        )

        is_device_info_service = "_device-info" in discovery_info.type
        has_valid_txt_properties = txt_properties and txt_properties != {"": None}

        # Extract device information from TXT records or service name
        if is_device_info_service and has_valid_txt_properties:
            result = await self._process_device_info_service(
                discovery_info, txt_properties
            )
        else:
            result = await self._process_standard_service(discovery_info)

        if result is not None:
            return result

        # Extract firmware version from discovery properties
        if discovery_info.properties:
            version = discovery_info.properties.get("version")
            if version:
                self._firmware_version = str(version)
                _LOGGER.debug(
                    "Firmware version from discovery: %s", self._firmware_version
                )

        # Set discovery card main title as device name
        if self._name:
            self.context["title_placeholders"] = {"name": self._name}

        _LOGGER.info(
            "Zeroconf device discovery: %s (Type: %s) at %s:%s, "
            "discovery_info.port=%s, discovery_info.type=%s, discovery_info.name=%s, "
            "properties=%s",
            self._name,
            self._device_type,
            self._host,
            self._port,
            discovery_info.port,
            discovery_info.type,
            discovery_info.name,
            discovery_info.properties,
        )

        # Use MAC address as unique_id if available (official HA pattern)
        # This ensures devices are identified by MAC, not by name/IP
        if self._mac:
            unique_id = format_mac(self._mac)
        else:
            # Try to extract MAC from device name (e.g., GDS_EC74D79753C5)
            extracted_mac = extract_mac_from_name(self._name or "")
            if extracted_mac:
                _LOGGER.info(
                    "Extracted MAC %s from device name %s, using as unique_id",
                    extracted_mac,
                    self._name,
                )
                unique_id = extracted_mac
            else:
                # Fallback to name-based unique_id if MAC not available
                unique_id = generate_unique_id(
                    self._name or "",
                    self._device_type or "",
                    self._host or "",
                    self._port,
                )

        _LOGGER.info(
            "Zeroconf discovery: Setting unique_id=%s for host=%s",
            unique_id,
            self._host,
        )

        # Abort any existing flows for this device to prevent duplicates
        await self._abort_all_flows_for_device(unique_id, self._host)

        _LOGGER.info(
            "Zeroconf discovery: About to set unique_id=%s, checking for existing flows",
            unique_id,
        )

        # Set unique_id and check if already configured
        # Use raise_on_progress=True to abort if another flow with same unique_id is in progress
        # This prevents duplicate discovery flows for the same device
        try:
            current_entry = await self.async_set_unique_id(
                unique_id, raise_on_progress=True
            )
        except AbortFlow:
            # Another flow is already in progress for this device
            _LOGGER.info(
                "Another discovery flow already in progress for %s, aborting",
                unique_id,
            )
            return self.async_abort(reason="already_in_progress")

        _LOGGER.info(
            "Zeroconf discovery: async_set_unique_id result - entry=%s, self.unique_id=%s",
            current_entry.unique_id
            if current_entry and current_entry.unique_id
            else None,
            self.unique_id,
        )
        if current_entry:
            current_host = current_entry.data.get(CONF_HOST)
            current_port = current_entry.data.get(CONF_PORT)

            _LOGGER.info(
                "Device %s discovered - current entry: host=%s, port=%s; "
                "discovery: host=%s, port=%s",
                unique_id,
                current_host,
                current_port,
                self._host,
                self._port,
            )

            # Check if host or port changed
            host_changed = current_host != self._host
            port_changed = current_port != self._port

            if not host_changed and not port_changed:
                # Same device, same IP and port - already configured
                _LOGGER.info(
                    "Device %s unchanged (same host and port), aborting discovery",
                    unique_id,
                )
                self._abort_if_unique_id_configured()
            else:
                # Same device, but IP or port changed - update and reload
                changes = []
                if host_changed:
                    changes.append(f"IP: {current_host} -> {self._host}")
                if port_changed:
                    changes.append(f"port: {current_port} -> {self._port}")

                _LOGGER.info(
                    "Device %s reconnected with changes: %s, reloading integration",
                    unique_id,
                    ", ".join(changes),
                )
                # Update the config entry with new IP, port and firmware version
                new_data = {
                    **current_entry.data,
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                }
                if self._firmware_version:
                    new_data[CONF_FIRMWARE_VERSION] = self._firmware_version

                self.hass.config_entries.async_update_entry(
                    current_entry,
                    data=new_data,
                )
                # Reload the integration to reconnect
                await self.hass.config_entries.async_reload(current_entry.entry_id)
                return self.async_abort(reason="already_configured")

        return await self.async_step_auth()

    async def _abort_existing_flow(self, unique_id: str) -> None:
        """Abort any existing in-progress flow with the same unique_id or host.

        This prevents "invalid flow specified" errors when a user tries to
        add a device again after a previous authentication failure.
        Also handles the case where a manually added device (name-based unique_id)
        needs to be converted to MAC-based unique_id.

        Args:
            unique_id: The unique ID to check for existing flows

        """
        if not self.hass:
            return

        # Get the flow manager and access in-progress flows
        flow_manager = self.hass.config_entries.flow
        flows_to_abort = []
        aborted_flow_ids = set()

        for flow in flow_manager.async_progress_by_handler(DOMAIN):
            # Skip the current flow
            if flow["flow_id"] == self.flow_id:
                continue

            should_abort = False

            # Abort flows with the same unique_id
            if flow.get("unique_id") == unique_id:
                should_abort = True
                _LOGGER.debug(
                    "Found existing flow %s with unique_id %s, will abort",
                    flow["flow_id"][:8],
                    unique_id[:8] if unique_id else "",
                )

            # Also abort flows with the same host (handles name-based to MAC-based conversion)
            if self._host and not should_abort:
                flow_unique_id = str(flow.get("unique_id", "") or "")
                if self._host in flow_unique_id:
                    should_abort = True
                    _LOGGER.debug(
                        "Found existing flow %s with same host %s in unique_id, will abort",
                        flow["flow_id"][:8],
                        self._host,
                    )

            if should_abort:
                flows_to_abort.append(flow["flow_id"])

        # Abort all matching flows
        for flow_id in flows_to_abort:
            if flow_id in aborted_flow_ids:
                continue
            aborted_flow_ids.add(flow_id)
            _LOGGER.info(
                "Aborting existing flow %s for unique_id %s",
                flow_id[:8],
                unique_id[:8] if unique_id else "",
            )
            try:
                flow_manager.async_abort(flow_id)
            except (OSError, ValueError, KeyError) as err:
                _LOGGER.warning(
                    "Failed to abort flow %s: %s",
                    flow_id[:8],
                    err,
                )

    async def _abort_all_flows_for_device(self, unique_id: str, host: str) -> None:
        """Abort ALL flows related to this device.

        This is a more aggressive cleanup that should be called when:
        - A device is discovered via zeroconf (to allow re-discovery after delete)
        - To ensure no stale flows are blocking new discovery

        Args:
            unique_id: The unique ID (MAC-based preferred)
            host: The device IP address

        """
        if not self.hass:
            return

        flow_manager = self.hass.config_entries.flow
        flows_to_abort = []

        _LOGGER.info(
            "Performing aggressive flow cleanup for device unique_id=%s, host=%s",
            unique_id,
            host,
        )

        for flow in flow_manager.async_progress_by_handler(DOMAIN):
            # Skip the current flow
            if flow["flow_id"] == self.flow_id:
                continue

            should_abort = False
            reason = ""

            # 1. Abort flows with the same unique_id (exact match)
            if flow.get("unique_id") == unique_id:
                should_abort = True
                reason = "same unique_id"

            # 2. Abort flows where host appears in unique_id (name-based unique_id)
            elif host and host in str(flow.get("unique_id", "") or ""):
                should_abort = True
                reason = "host in unique_id"

            # 3. Abort flows with same host in context (for flows that haven't set unique_id yet)
            elif host:
                context = flow.get("context", {})
                # Check title_placeholders or other context data
                if context.get("host") == host:
                    should_abort = True
                    reason = "host in context"

            if should_abort:
                flows_to_abort.append((flow["flow_id"], reason))
                _LOGGER.debug(
                    "Found flow %s to abort (reason: %s)",
                    flow["flow_id"][:8],
                    reason,
                )

        # Abort all matching flows
        for flow_id, reason in flows_to_abort:
            _LOGGER.info(
                "Aborting flow %s for device %s (reason: %s)",
                flow_id[:8],
                host,
                reason,
            )
            try:
                flow_manager.async_abort(flow_id)
            except (OSError, ValueError, KeyError) as err:
                _LOGGER.warning(
                    "Failed to abort flow %s: %s",
                    flow_id[:8],
                    err,
                )

    async def _process_device_info_service(
        self, discovery_info: Any, txt_properties: dict[str, Any]
    ) -> config_entries.ConfigFlowResult | None:
        """Process device info service discovery."""
        # Check if this is a Grandstream device
        product_name = txt_properties.get("product_name", "")
        product = txt_properties.get("product", "")
        hostname = txt_properties.get("hostname", "")
        service_name = discovery_info.name.split(".")[0] if discovery_info.name else ""

        is_grandstream = (
            is_grandstream_device(product_name)
            or is_grandstream_device(product)
            or is_grandstream_device(hostname)
            or is_grandstream_device(service_name)
        )

        if not is_grandstream:
            _LOGGER.debug(
                "Ignoring non-Grandstream device: %s", hostname or product_name
            )
            return self.async_abort(reason="not_grandstream_device")

        # Extract device info using library function
        device_info = get_device_info_from_txt(txt_properties)

        self._product_model = device_info["product_model"]
        self._device_type = device_info["device_type"]
        self._device_model = device_info["device_model"]
        self._mac = device_info["mac"]

        # Device name - prefer hostname
        self._name = hostname or product_name or service_name
        if self._name:
            self._name = self._name.strip().upper()

        # Extract port
        self._port = extract_port_from_txt(txt_properties, DEFAULT_HTTPS_PORT)

        _LOGGER.debug(
            "Device info - hostname: %s, product: %s, version: %s",
            device_info["hostname"],
            self._product_model,
            device_info["version"],
        )
        return None

    async def _process_standard_service(
        self, discovery_info: Any
    ) -> config_entries.ConfigFlowResult | None:
        """Process standard service discovery."""
        # Only process HTTPS services
        service_type = discovery_info.type or ""
        if "_https._tcp" not in service_type:
            _LOGGER.debug("Ignoring non-HTTPS service: %s", service_type)
            return self.async_abort(reason="not_grandstream_device")

        # Get TXT properties and extract device info
        txt_properties = discovery_info.properties or {}
        device_info = get_device_info_from_txt(txt_properties)

        # Device name from service name
        self._name = (
            discovery_info.name.split(".")[0].upper() if discovery_info.name else ""
        )

        # Check if this is a Grandstream device
        if not is_grandstream_device(self._name):
            _LOGGER.debug("Ignoring non-Grandstream device: %s", self._name)
            return self.async_abort(reason="not_grandstream_device")

        # Use device info from TXT if available, otherwise fallback to name
        if device_info["product_model"]:
            self._product_model = device_info["product_model"]
            self._device_type = device_info["device_type"]
            self._device_model = device_info["device_model"]
        else:
            # Fallback to name-based detection
            self._product_model = None
            self._device_type = determine_device_type_from_product(self._name)
            self._device_model = get_device_model_from_product(self._name)

        # Set port
        self._port = discovery_info.port or DEFAULT_PORT

        return None

    async def _validate_credentials(
        self, username: str, password: str, port: int, verify_ssl: bool
    ) -> str | None:
        """Validate credentials by attempting to connect to the device."""
        if not self._host or not self._device_type:
            return "missing_data"

        try:
            api = create_api_instance(
                device_type=self._device_type,
                host=self._host,
                username=username,
                password=password,
                port=port,
                verify_ssl=verify_ssl,
            )
            success, error_type = await self.hass.async_add_executor_job(
                attempt_login, api
            )
        except OSError as err:
            _LOGGER.warning("Connection error during credential validation: %s", err)
            return "cannot_connect"

        if error_type == "ha_control_disabled":
            _LOGGER.warning("Home Assistant control is disabled on the device")
            return "ha_control_disabled"

        if error_type == "offline":
            _LOGGER.warning("Device is offline or unreachable")
            return "cannot_connect"

        if not success:
            return "invalid_auth"

        # Get MAC address from API after successful login
        if hasattr(api, "device_mac") and api.device_mac:
            self._mac = api.device_mac
            _LOGGER.info("Got MAC address from device API: %s", self._mac)

        return None

    async def _update_unique_id_for_mac(
        self,
    ) -> config_entries.ConfigFlowResult | None:
        """Update unique_id to MAC-based if MAC is available.

        Returns:
            async_abort if device already configured, None otherwise

        """
        # Determine the unique_id to use
        if self._mac:
            new_unique_id = format_mac(self._mac)
        else:
            # No MAC available, use name-based unique_id
            new_unique_id = generate_unique_id(
                self._name or "", self._device_type or "", self._host or "", self._port
            )
            _LOGGER.info(
                "No MAC available, using name-based unique_id: %s", new_unique_id
            )

        if new_unique_id == self.unique_id:
            return None

        _LOGGER.info(
            "Setting unique_id to %s (MAC-based: %s)",
            new_unique_id[:8],
            bool(self._mac),
        )

        # Use raise_on_progress=False to avoid conflicts with other flows
        existing_entry = await self.async_set_unique_id(
            new_unique_id, raise_on_progress=False
        )

        if existing_entry:
            current_host = existing_entry.data.get(CONF_HOST)
            if current_host != self._host:
                # Same device, different IP - update IP and reload
                _LOGGER.info(
                    "Device %s reconnected with new IP: %s -> %s, updating config",
                    new_unique_id,
                    current_host,
                    self._host,
                )
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={**existing_entry.data, CONF_HOST: self._host},
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="already_configured")

        # Verify unique_id was set correctly
        _LOGGER.info(
            "Unique_id set successfully: self.unique_id=%s",
            self.unique_id[:8] if self.unique_id else None,
        )

        return None

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle authentication step.

        Args:
            user_input: User input data from the form

        Returns:
            FlowResult: Next step or form to show

        """
        errors: dict[str, str] = {}

        # Determine if device is GNS type
        default_username = get_default_username(self._device_type or DEVICE_TYPE_GDS)

        # Get current form values (preserve on validation error)
        current_username = (
            user_input.get(CONF_USERNAME, default_username)
            if user_input
            else default_username
        )
        current_password = user_input.get(CONF_PASSWORD, "") if user_input else ""
        # For port, use validated port or original port
        current_port = self._port
        if user_input:
            port_value = user_input.get(CONF_PORT, str(self._port))
            is_valid, port = validate_port(port_value)
            if is_valid:
                current_port = port

        # No user input - show form
        if user_input is None:
            return self._show_auth_form(
                default_username,
                current_username,
                current_password,
                current_port,
                errors,
            )

        # Validate port number
        port_value = user_input.get(CONF_PORT, str(DEFAULT_PORT))
        is_valid, port = validate_port(port_value)
        if not is_valid:
            errors["port"] = "invalid_port"
            return self._show_auth_form(
                default_username,
                current_username,
                current_password,
                current_port,
                errors,
            )

        # Validate credentials
        verify_ssl = user_input.get(CONF_VERIFY_SSL, False)
        username = user_input.get(CONF_USERNAME, default_username)
        password = user_input[CONF_PASSWORD]

        validation_result = await self._validate_credentials(
            username, password, port, verify_ssl
        )

        if validation_result is not None:
            errors["base"] = validation_result
            _LOGGER.warning("Credential validation failed: %s", validation_result)
            return self._show_auth_form(
                default_username,
                current_username,
                current_password,
                current_port,
                errors,
            )

        # Validation successful - update port
        self._port = port

        # Update unique_id to MAC-based if available
        abort_result = await self._update_unique_id_for_mac()
        if abort_result:
            return abort_result

        # Store auth info
        self._auth_info = {
            CONF_USERNAME: username,
            CONF_PASSWORD: encrypt_password(password, self.unique_id or "default"),
            CONF_PORT: port,
            CONF_VERIFY_SSL: verify_ssl,
        }

        return await self._create_config_entry()

    def _show_auth_form(
        self,
        default_username: str,
        current_username: str,
        current_password: str,
        current_port: int,
        errors: dict[str, str],
    ) -> config_entries.ConfigFlowResult:
        """Show authentication form.

        Args:
            default_username: Default username for device type
            current_username: Current username value
            current_password: Current password value
            current_port: Current port value
            errors: Form errors

        Returns:
            Form display result

        """
        # Build form schema
        schema_dict = self._build_auth_schema(
            self._device_type == DEVICE_TYPE_GNS_NAS,
            current_username,
            current_password,
            current_port,
        )

        # Build description placeholders
        # Display product_model if available, otherwise device_model, then device_type
        display_model = (
            self._product_model or self._device_model or self._device_type or ""
        )
        description_placeholders = {
            "host": self._host or "",
            "device_model": display_model,
            "username": default_username,
        }

        return self.async_show_form(
            step_id="auth",
            description_placeholders=description_placeholders,
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    def _build_auth_schema(
        self,
        is_gns_device: bool,
        current_username: str,
        current_password: str,
        current_port: int,
    ) -> dict:
        """Build authentication form schema.

        Args:
            is_gns_device: Whether the device is GNS type
            current_username: Current username value
            current_password: Current password value
            current_port: Current port value

        Returns:
            dict: Form schema dictionary

        """
        schema_dict: dict[Any, Any] = {}

        # GNS devices need username input, GDS uses fixed username
        if is_gns_device:
            schema_dict[vol.Required(CONF_USERNAME, default=current_username)] = (
                cv.string
            )

        schema_dict.update(
            {
                vol.Required(CONF_PASSWORD, default=current_password): cv.string,
                vol.Optional(CONF_PORT, default=current_port): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
            }
        )

        return schema_dict

    async def _create_config_entry(self) -> config_entries.ConfigFlowResult:
        """Create the config entry.

        Returns:
            FlowResult: Configuration entry creation result

        """
        _LOGGER.info("Creating config entry for device: %s", self._name)

        # Ensure required data is available
        if not self._name or not self._host or not self._auth_info:
            _LOGGER.error("Missing required configuration data")
            return self.async_abort(reason="missing_data")

        # Use device type from user selection or default to GDS
        device_type = self._device_type or DEVICE_TYPE_GDS

        # Use the already-set unique_id (set in async_step_auth after MAC is obtained)
        unique_id = self.unique_id
        if not unique_id:
            # Fallback: should not happen if _update_unique_id_for_mac worked correctly
            _LOGGER.warning("Unique_id not set, generating fallback unique_id")
            if self._mac:
                unique_id = format_mac(self._mac)
            else:
                unique_id = generate_unique_id(
                    self._name, device_type, self._host, self._port
                )
            await self.async_set_unique_id(unique_id)

        _LOGGER.info("Creating config entry with unique_id: %s", unique_id)

        # Check if already configured (should not happen as we checked earlier)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        # Get username from auth_info (user input) or use default based on device type
        username = self._auth_info.get(CONF_USERNAME)
        if not username:
            username = (
                DEFAULT_USERNAME_GNS
                if device_type == DEVICE_TYPE_GNS_NAS
                else DEFAULT_USERNAME
            )

        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._auth_info.get(CONF_PORT, DEFAULT_PORT),
            CONF_NAME: self._name,
            CONF_USERNAME: username,
            CONF_PASSWORD: self._auth_info[CONF_PASSWORD],
            CONF_DEVICE_TYPE: device_type,
            CONF_DEVICE_MODEL: self._device_model or device_type,
            CONF_VERIFY_SSL: self._auth_info.get(CONF_VERIFY_SSL, False),
        }

        # Add product model if available (specific model like GDS3725, GDS3727, GSC3560)
        if self._product_model:
            data[CONF_PRODUCT_MODEL] = self._product_model

        # Add firmware version from discovery if available
        if self._firmware_version:
            data[CONF_FIRMWARE_VERSION] = self._firmware_version

        _LOGGER.info("Creating config entry: %s, unique ID: %s", self._name, unique_id)
        return self.async_create_entry(
            title=self._name,
            data=data,
        )

    # Reauthentication Flow
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication when credentials are invalid.

        Args:
            entry_data: Current config entry data

        Returns:
            FlowResult: Next step in reauthentication flow

        """
        _LOGGER.info("Starting reauthentication for %s", entry_data.get(CONF_HOST))

        # Store current config for reuse
        self._host = entry_data.get(CONF_HOST)
        self._name = entry_data.get(CONF_NAME)
        self._port = entry_data.get(CONF_PORT, DEFAULT_PORT)
        self._device_type = entry_data.get(CONF_DEVICE_TYPE)
        self._device_model = entry_data.get(CONF_DEVICE_MODEL)
        self._product_model = entry_data.get(CONF_PRODUCT_MODEL)

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication confirmation.

        Args:
            user_input: User input data from the form

        Returns:
            FlowResult: Reauthentication result

        """
        errors = {}

        if user_input is not None:
            # Validate new credentials
            is_gns_device = self._device_type == DEVICE_TYPE_GNS_NAS
            default_username = (
                DEFAULT_USERNAME_GNS if is_gns_device else DEFAULT_USERNAME
            )

            # Use provided username or default
            username = user_input.get(CONF_USERNAME, default_username)
            password = user_input[CONF_PASSWORD]

            # Test connection with new credentials
            try:
                api = create_api_instance(
                    device_type=self._device_type or "",
                    host=self._host or "",
                    username=username,
                    password=password,
                    port=self._port,
                    verify_ssl=False,
                )

                success, error_type = await self.hass.async_add_executor_job(
                    attempt_login, api
                )

                if error_type == "ha_control_disabled":
                    errors["base"] = "ha_control_disabled"
                elif error_type == "offline":
                    errors["base"] = "cannot_connect"
                elif not success:
                    errors["base"] = "invalid_auth"

            except GrandstreamError, OSError, TimeoutError:
                errors["base"] = "invalid_auth"

            if not errors:
                _LOGGER.info("Reauthentication successful for %s", self._host)

                # Get the config entry being reauthenticated
                reauth_entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if not reauth_entry:
                    return self.async_abort(reason="reauth_entry_not_found")

                # Update the config entry with new credentials
                encrypted_password = encrypt_password(
                    password, reauth_entry.unique_id or "default"
                )

                # Preserve existing SSL verification setting
                verify_ssl = reauth_entry.data.get(CONF_VERIFY_SSL, False)

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: encrypted_password,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                    reason="reauth_successful",
                )

        # Build form schema
        is_gns_device = self._device_type == DEVICE_TYPE_GNS_NAS
        default_username = DEFAULT_USERNAME_GNS if is_gns_device else DEFAULT_USERNAME

        schema_dict: dict[Any, Any] = {}
        if is_gns_device:
            schema_dict[vol.Required(CONF_USERNAME, default=default_username)] = (
                cv.string
            )
        schema_dict[vol.Required(CONF_PASSWORD)] = cv.string

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "host": self._host or "",
                "device_model": self._product_model
                or self._device_model
                or self._device_type
                or "",
            },
        )

    # Reconfiguration Flow
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration flow.

        This allows users to reconfigure the device from the UI
        (Settings > Devices & Services > Reconfigure).

        Args:
            user_input: User input data from the form

        Returns:
            FlowResult: Reconfiguration result

        """
        errors: dict[str, str] = {}

        # Get the config entry being reconfigured
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return self.async_abort(reason="no_entry_id")

        config_entry = self.hass.config_entries.async_get_entry(entry_id)
        if not config_entry:
            return self.async_abort(reason="no_config_entry")

        current_data = config_entry.data
        is_gns_device = current_data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_GNS_NAS

        if user_input is not None:
            # Validate IP address
            if not validate_ip_address(user_input[CONF_HOST]):
                errors["host"] = "invalid_host"

            # Validate port number
            port_value = user_input.get(CONF_PORT, str(DEFAULT_PORT))
            is_valid, port = validate_port(port_value)
            if not is_valid:
                errors["port"] = "invalid_port"
                port = current_data.get(CONF_PORT, DEFAULT_PORT)

            if not errors:
                # Validate credentials
                try:
                    username = (
                        user_input.get(CONF_USERNAME)
                        if is_gns_device
                        else current_data.get(CONF_USERNAME, DEFAULT_USERNAME)
                    )
                    password = user_input[CONF_PASSWORD]
                    verify_ssl = user_input.get(CONF_VERIFY_SSL, False)
                    device_type = current_data.get(CONF_DEVICE_TYPE, "")
                    host = user_input[CONF_HOST].strip()

                    api = create_api_instance(
                        device_type=device_type,
                        host=host,
                        username=username or "",
                        password=password,
                        port=port,
                        verify_ssl=verify_ssl,
                    )

                    success, error_type = await self.hass.async_add_executor_job(
                        attempt_login, api
                    )

                    if error_type == "ha_control_disabled":
                        errors["base"] = "ha_control_disabled"
                    elif error_type == "offline":
                        errors["base"] = "cannot_connect"
                    elif not success:
                        errors["base"] = "invalid_auth"

                except GrandstreamError, OSError, TimeoutError:
                    errors["base"] = "cannot_connect"

            if not errors:
                _LOGGER.info(
                    "Reconfiguration successful for %s", user_input.get(CONF_HOST)
                )

                # Build updated data
                updated_data = dict(current_data)

                # Encrypt passwords if not already encrypted
                password = user_input[CONF_PASSWORD]
                if not password.startswith("encrypted:"):
                    password = encrypt_password(
                        password, config_entry.unique_id or "default"
                    )

                updated_data.update(
                    {
                        CONF_HOST: user_input[CONF_HOST].strip(),
                        CONF_PORT: port,
                        CONF_USERNAME: user_input.get(CONF_USERNAME)
                        if is_gns_device
                        else current_data.get(CONF_USERNAME, DEFAULT_USERNAME),
                        CONF_PASSWORD: password,
                        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, False),
                    }
                )

                return self.async_update_reload_and_abort(
                    config_entry,
                    data_updates=updated_data,
                    reason="reconfigure_successful",
                )

        # Build form schema with current values as defaults
        schema_dict: dict[Any, Any] = {
            vol.Required(
                CONF_HOST,
                default=user_input.get(CONF_HOST)
                if user_input
                else current_data.get(CONF_HOST, ""),
            ): cv.string,
            vol.Optional(
                CONF_PORT,
                default=user_input.get(CONF_PORT)
                if user_input
                else current_data.get(CONF_PORT, DEFAULT_PORT),
            ): cv.string,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=user_input.get(CONF_VERIFY_SSL)
                if user_input is not None
                else current_data.get(CONF_VERIFY_SSL, False),
            ): cv.boolean,
        }

        # Only show username field for GNS devices
        if is_gns_device:
            schema_dict[
                vol.Required(
                    CONF_USERNAME,
                    default=user_input.get(CONF_USERNAME)
                    if user_input
                    else current_data.get(CONF_USERNAME, DEFAULT_USERNAME_GNS),
                )
            ] = cv.string

        # Password field - don't show encrypted password as default
        password_default = user_input.get(CONF_PASSWORD, "") if user_input else ""
        schema_dict[vol.Required(CONF_PASSWORD, default=password_default)] = cv.string

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "name": current_data.get(CONF_NAME, ""),
                "device_model": current_data.get(
                    CONF_PRODUCT_MODEL,
                    current_data.get(
                        CONF_DEVICE_MODEL, current_data.get(CONF_DEVICE_TYPE, "")
                    ),
                ),
            },
        )
