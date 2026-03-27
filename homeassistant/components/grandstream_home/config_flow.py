"""Config flow for Grandstream Home."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from grandstream_home_api import GDSPhoneAPI, GNSNasAPI
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
    CONF_USE_HTTPS,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTPS_PORT,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEFAULT_USERNAME_GNS,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DEVICE_TYPE_GSC,
    DOMAIN,
)
from .error import GrandstreamError, GrandstreamHAControlDisabledError
from .utils import (
    encrypt_password,
    extract_mac_from_name,
    generate_unique_id,
    mask_sensitive_data,
    validate_ip_address,
    validate_port,
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
        self._use_https: bool = True  # Track if using HTTPS protocol
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
                self._device_type = user_input[CONF_DEVICE_TYPE]

                # Save original device model and map GSC to GDS internally
                if self._device_type == DEVICE_TYPE_GSC:
                    self._device_model = DEVICE_TYPE_GSC
                    self._device_type = DEVICE_TYPE_GDS  # GSC uses GDS internally
                else:
                    self._device_model = self._device_type

                # Set default port based on device type
                # GNS NAS devices default to DEFAULT_HTTPS_PORT (5001), GDS devices default to 443 (HTTPS)
                if self._device_type == DEVICE_TYPE_GNS_NAS:
                    self._port = DEFAULT_HTTPS_PORT
                    self._use_https = True
                else:
                    # GDS/GSC devices default to HTTPS (port 443)
                    self._port = DEFAULT_PORT  # 443
                    self._use_https = True

                # For manual addition, DON'T set a unique_id yet
                # It will be set later in _update_unique_id_for_mac after we get the MAC address
                # This prevents name-based unique_id conflicts with future zeroconf discovery
                _LOGGER.info(
                    "Manual device addition: %s (Type: %s), waiting for MAC to set unique_id",
                    self._name,
                    self._device_type,
                )
                return await self.async_step_auth()

        # Show form with input fields
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPE_GDS): vol.In(
                        [DEVICE_TYPE_GDS, DEVICE_TYPE_GSC, DEVICE_TYPE_GNS_NAS]
                    ),
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
            "Zeroconf device discovery: %s (Type: %s) at %s:%s, use_https=%s, "
            "discovery_info.port=%s, discovery_info.type=%s, discovery_info.name=%s, "
            "properties=%s",
            self._name,
            self._device_type,
            self._host,
            self._port,
            self._use_https,
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

    def _is_grandstream(self, product_name):
        """Check if the device is a Grandstream device.

        Args:
            product_name: Product name to check

        Returns:
            bool: True if it's a Grandstream device

        """
        return any(
            prefix in str(product_name).upper()
            for prefix in (DEVICE_TYPE_GNS_NAS, DEVICE_TYPE_GDS, DEVICE_TYPE_GSC)
        )

    async def _process_device_info_service(
        self, discovery_info: Any, txt_properties: dict[str, Any]
    ) -> config_entries.ConfigFlowResult | None:
        """Process device info service discovery.

        Args:
            discovery_info: Zeroconf discovery information
            txt_properties: TXT record properties

        Returns:
            ConfigFlowResult if device should be ignored, None otherwise

        """
        _LOGGER.debug("txt_properties:%s", txt_properties)

        # Check if this is a Grandstream device by examining TXT records
        product_name = txt_properties.get("product_name", "")
        product = txt_properties.get("product", "")  # Also check 'product' field
        hostname = txt_properties.get("hostname", "")
        # Also check discovery_info.name for device type
        service_name = discovery_info.name.split(".")[0] if discovery_info.name else ""

        # Check if this is a Grandstream device by product_name, product, hostname, or service name
        is_grandstream = (
            self._is_grandstream(product_name)
            or self._is_grandstream(product)
            or self._is_grandstream(hostname)
            or self._is_grandstream(service_name)
        )

        if not is_grandstream:
            _LOGGER.debug(
                "Ignoring non-Grandstream device: %s (product: %s, hostname: %s, service: %s)",
                hostname,
                product_name or product,
                hostname,
                service_name,
            )
            return self.async_abort(reason="not_grandstream_device")

        # Extract product model from 'product' field first, then 'product_name' field
        # GDS devices use 'product' field (e.g., product=GDS3725)
        # GNS devices use 'product_name' field (e.g., product_name=GNS5004E)
        if product:
            self._product_model = str(product).strip().upper()
            _LOGGER.info(
                "Product model from TXT record 'product': %s", self._product_model
            )
        elif product_name:
            self._product_model = str(product_name).strip().upper()
            _LOGGER.info(
                "Product model from TXT record 'product_name': %s", self._product_model
            )

        # Determine device type and name based on product_name or product
        self._device_type = self._determine_device_type_from_product(txt_properties)

        # Extract device name - prefer hostname for device-info service
        if hostname:
            self._name = str(hostname).strip().upper()
        elif product_name:
            self._name = str(product_name).strip().upper()
        else:
            self._name = (
                discovery_info.name.split(".")[0] if discovery_info.name else ""
            )

        # Extract port and protocol from TXT records
        self._extract_port_and_protocol(txt_properties, is_https_default=True)

        # GDS/GSC devices always use HTTPS
        if self._device_type == DEVICE_TYPE_GDS:
            self._use_https = True

        # Extract MAC address if available
        # GNS devices may have multiple MACs separated by comma, use the first one
        mac = txt_properties.get("mac")
        if mac:
            mac_str = str(mac).strip()
            # Handle multiple MACs (e.g., "ec:74:d7:61:a6:85,ec:74:d7:61:a6:86,...")
            if "," in mac_str:
                mac_str = mac_str.split(",", maxsplit=1)[0].strip()
            self._mac = mac_str
            _LOGGER.debug(
                "Zeroconf provided MAC: %s (will be verified/updated after login)",
                self._mac,
            )

        # Log additional device information
        self._log_device_info(txt_properties)
        return None

    async def _process_standard_service(
        self, discovery_info: Any
    ) -> config_entries.ConfigFlowResult | None:
        """Process standard service discovery.

        Args:
            discovery_info: Zeroconf discovery information

        Returns:
            ConfigFlowResult if device should be ignored, None otherwise

        """
        # Only process HTTPS services (_https._tcp.local.)
        # Ignore other services like SSH, HTTP, Web Site, etc.
        service_type = discovery_info.type or ""
        if "_https._tcp" not in service_type:
            _LOGGER.debug(
                "Ignoring non-HTTPS service for %s: %s",
                discovery_info.name,
                service_type,
            )
            return self.async_abort(reason="not_grandstream_device")

        # Get TXT properties
        txt_properties = discovery_info.properties or {}

        # For HTTP/HTTPS services or services without valid TXT records
        self._name = (
            discovery_info.name.split(".")[0].upper() if discovery_info.name else ""
        )

        # Check if this is a Grandstream device
        is_grandstream = self._is_grandstream(self._name)

        if not is_grandstream:
            _LOGGER.debug("Ignoring non-Grandstream device: %s", self._name)
            return self.async_abort(reason="not_grandstream_device")

        # Extract product model from TXT records (e.g., product=GDS3725)
        product = txt_properties.get("product")
        if product:
            self._product_model = str(product).strip().upper()
            _LOGGER.info("Product model from TXT record: %s", self._product_model)

        # Set device type based on product model first, then name
        if self._product_model:
            # Use product model to determine device type
            if self._product_model.startswith(DEVICE_TYPE_GSC):
                self._device_model = DEVICE_TYPE_GSC
                self._device_type = DEVICE_TYPE_GDS  # GSC uses GDS internally
            elif self._product_model.startswith(DEVICE_TYPE_GNS_NAS):
                self._device_model = DEVICE_TYPE_GNS_NAS
                self._device_type = DEVICE_TYPE_GNS_NAS
            else:
                # GDS models (GDS3725, GDS3727, etc.)
                self._device_model = DEVICE_TYPE_GDS
                self._device_type = DEVICE_TYPE_GDS
        elif DEVICE_TYPE_GNS_NAS in self._name.upper():
            self._device_type = DEVICE_TYPE_GNS_NAS
            self._device_model = DEVICE_TYPE_GNS_NAS
        elif DEVICE_TYPE_GSC in self._name.upper():
            self._device_model = DEVICE_TYPE_GSC  # Save original model
            self._device_type = DEVICE_TYPE_GDS  # GSC uses GDS internally
        elif DEVICE_TYPE_GDS in self._name.upper():
            self._device_type = DEVICE_TYPE_GDS
            self._device_model = DEVICE_TYPE_GDS
        else:
            # Default fallback
            self._device_type = DEVICE_TYPE_GDS
            self._device_model = DEVICE_TYPE_GDS

        # Set port and protocol
        self._port = discovery_info.port or DEFAULT_PORT
        self._use_https = True  # GDS/GSC always uses HTTPS

        return None

    def _is_gns_device(self) -> bool:
        """Check if current device is GNS type."""
        return self._device_type == DEVICE_TYPE_GNS_NAS

    def _get_default_username(self) -> str:
        """Get default username based on device type."""
        return DEFAULT_USERNAME_GNS if self._is_gns_device() else DEFAULT_USERNAME

    def _create_api_for_validation(
        self,
        host: str,
        username: str,
        password: str,
        port: int,
        device_type: str,
        verify_ssl: bool = False,
    ) -> GDSPhoneAPI | GNSNasAPI:
        """Create API instance for credential validation."""
        if device_type == DEVICE_TYPE_GNS_NAS:
            use_https = port == DEFAULT_HTTPS_PORT
            return GNSNasAPI(
                host,
                username,
                password,
                port=port,
                use_https=use_https,
                verify_ssl=verify_ssl,
            )
        return GDSPhoneAPI(
            host=host,
            username=username,
            password=password,
            port=port,
            verify_ssl=verify_ssl,
        )

    async def _validate_credentials(
        self, username: str, password: str, port: int, verify_ssl: bool
    ) -> str | None:
        """Validate credentials by attempting to connect to the device.

        Args:
            username: Username for authentication
            password: Password for authentication
            port: Port number
            verify_ssl: Whether to verify SSL certificate

        Returns:
            Error message key if validation failed, None if successful

        """
        if not self._host or not self._device_type:
            return "missing_data"

        try:
            api = self._create_api_for_validation(
                self._host, username, password, port, self._device_type, verify_ssl
            )
            # Attempt login
            success = await self.hass.async_add_executor_job(api.login)
        except GrandstreamHAControlDisabledError:
            # HA control is disabled on the device
            _LOGGER.warning("Home Assistant control is disabled on the device")
            return "ha_control_disabled"
        except OSError as err:
            _LOGGER.warning("Connection error during credential validation: %s", err)
            return "cannot_connect"
        except (ValueError, KeyError, AttributeError) as err:
            _LOGGER.warning("Unexpected error during credential validation: %s", err)
            return "invalid_auth"

        if not success:
            return "invalid_auth"

        # Get MAC address from API after successful login
        # Both GDS and GNS APIs populate device_mac during login:
        # - GDS: Gets MAC from login response body
        # - GNS: Calls _fetch_device_mac() to get primary interface MAC
        zeroconf_mac = self._mac  # Save Zeroconf MAC for comparison

        if hasattr(api, "device_mac") and api.device_mac:
            self._mac = api.device_mac
            if zeroconf_mac and zeroconf_mac != self._mac:
                _LOGGER.info(
                    "MAC address updated from Zeroconf (%s) to device API (%s)",
                    zeroconf_mac,
                    self._mac,
                )
            else:
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
        _LOGGER.info("Async_step_auth %s", mask_sensitive_data(user_input))

        # Determine if device is GNS type
        default_username = self._get_default_username()

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

        # Validation successful - update protocol and port
        # GDS/GSC devices always use HTTPS
        if self._device_type == DEVICE_TYPE_GDS:
            self._use_https = True
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
            self._is_gns_device(),
            current_username,
            current_password,
            current_port,
            None,
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
        user_input: dict[str, Any] | None,
    ) -> dict:
        """Build authentication form schema.

        Args:
            is_gns_device: Whether the device is GNS type
            current_username: Current username value
            current_password: Current password value
            current_port: Current port value
            user_input: User input data (for preserving form fields)

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

    def _determine_device_type_from_product(
        self, txt_properties: dict[str, Any]
    ) -> str:
        """Determine device type based on product_name or product from TXT records.

        Args:
            txt_properties: TXT record properties from Zeroconf discovery

        Returns:
            str: Device type constant (DEVICE_TYPE_GNS_NAS or DEVICE_TYPE_GDS)

        """
        # Prefer already extracted product model (from 'product' field)
        if self._product_model:
            product_name = self._product_model
        else:
            product_name = txt_properties.get("product_name", "").strip().upper()

        if not product_name:
            _LOGGER.debug(
                "No product_name or product found in TXT records, defaulting to GDS"
            )
            self._device_model = DEVICE_TYPE_GDS
            return DEVICE_TYPE_GDS

        _LOGGER.debug("Determining device type from product: %s", product_name)

        # Check if product name starts with GNS
        if product_name.startswith(DEVICE_TYPE_GNS_NAS):
            _LOGGER.debug("Matched GNS device from product")
            self._device_model = DEVICE_TYPE_GNS_NAS
            return DEVICE_TYPE_GNS_NAS

        # Check if product name starts with GSC
        if product_name.startswith(DEVICE_TYPE_GSC):
            _LOGGER.debug("Matched GSC device from product")
            self._device_model = DEVICE_TYPE_GSC
            return DEVICE_TYPE_GDS  # GSC uses GDS internally

        # Default to GDS for all other cases
        _LOGGER.debug("Defaulting to GDS device type")
        self._device_model = DEVICE_TYPE_GDS
        return DEVICE_TYPE_GDS

    def _extract_port_and_protocol(
        self, txt_properties: dict[str, Any], is_https_default: bool = True
    ) -> None:
        """Extract port and protocol information from TXT records.

        Args:
            txt_properties: TXT record properties
            is_https_default: Whether to default to HTTPS if no port found

        """
        https_port = txt_properties.get("https_port")
        http_port = txt_properties.get("http_port")

        if https_port:
            try:
                self._port = int(https_port)
                self._use_https = True
            except (ValueError, TypeError) as _:
                _LOGGER.warning("Invalid https_port value: %s", https_port)
            else:
                return

        if http_port:
            try:
                self._port = int(http_port)
                self._use_https = False
            except (ValueError, TypeError) as _:
                _LOGGER.warning("Invalid http_port value: %s", http_port)
            else:
                return

        # Default values if no valid port found
        if is_https_default:
            self._port = DEFAULT_HTTPS_PORT
            self._use_https = True
        else:
            self._port = DEFAULT_HTTP_PORT
            self._use_https = False

    def _log_device_info(self, txt_properties: dict[str, Any]) -> None:
        """Log device information from TXT records.

        Args:
            txt_properties: TXT record properties

        """
        info_fields = {
            "hostname": "Device hostname",
            "product_name": "Device product",
            "version": "Firmware version",
            "mac": "MAC address",
        }

        for field, label in info_fields.items():
            value = txt_properties.get(field)
            if value:
                _LOGGER.debug("%s: %s", label, value)

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
            CONF_USE_HTTPS: self._use_https,
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
        self._use_https = entry_data.get(CONF_USE_HTTPS, True)

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
                # Create API instance to test credentials
                api = self._create_api_for_validation(
                    self._host or "",
                    username,
                    password,
                    self._port,
                    self._device_type or "",
                    False,
                )

                # Test login
                success = await self.hass.async_add_executor_job(api.login)
                if not success:
                    errors["base"] = "invalid_auth"

            except GrandstreamHAControlDisabledError:
                errors["base"] = "ha_control_disabled"
            except (GrandstreamError, OSError, TimeoutError) as _:
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

                    api = self._create_api_for_validation(
                        host, username or "", password, port, device_type, verify_ssl
                    )

                    success = await self.hass.async_add_executor_job(api.login)
                    if not success:
                        errors["base"] = "invalid_auth"

                except GrandstreamHAControlDisabledError:
                    errors["base"] = "ha_control_disabled"
                except (GrandstreamError, OSError, TimeoutError) as _:
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
