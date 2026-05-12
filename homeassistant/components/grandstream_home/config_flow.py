"""Config flow for Grandstream Home."""

import logging
from typing import Any

from grandstream_home_api import (
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GSC,
    attempt_login,
    create_api_instance,
    extract_mac_from_name,
    validate_port,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_DEVICE_MODEL,
    CONF_FIRMWARE_VERSION,
    CONF_PRODUCT_MODEL,
    CONF_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GrandstreamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grandstream Home."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._port: int = DEFAULT_PORT
        self._mac: str | None = None
        self._firmware_version: str | None = None
        self._device_model: str = DEVICE_TYPE_GDS
        self._product_model: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step for manual addition."""
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            self._port = DEFAULT_PORT
            # Name will be set after successful authentication from device info
            self._name = ""

            _LOGGER.debug(
                "Manual device addition at %s:%s",
                self._host,
                self._port,
            )

            return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                }
            ),
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle zeroconf discovery callback."""
        self._host = discovery_info.host
        txt_properties = discovery_info.properties or {}

        _LOGGER.debug(
            "Zeroconf discovery - Host: %s, Port: %s, Name: %s",
            self._host,
            discovery_info.port,
            discovery_info.name,
        )

        # Device name from service name
        name = discovery_info.name
        if name:
            self._name = str(name).split(".", maxsplit=1)[0].upper()
        else:
            self._name = ""

        # Check if this is a supported device (GDS or GSC)
        if self._name.startswith("GDS"):
            self._device_model = DEVICE_TYPE_GDS
        elif self._name.startswith("GSC"):
            self._device_model = DEVICE_TYPE_GSC

        self._port = discovery_info.port or DEFAULT_PORT

        # Extract firmware version and product model from discovery properties
        if txt_properties:
            version = txt_properties.get("version")
            if version:
                self._firmware_version = str(version)
            self._product_model = txt_properties.get("product")

        if self._name:
            self.context["title_placeholders"] = {"name": self._name}

        # Use MAC address as unique_id if available
        self._mac = extract_mac_from_name(self._name)
        # Set unique_id and check if already configured
        if self._mac:
            await self.async_set_unique_id(format_mac(self._mac))
        else:
            # For devices without MAC, use host+port to check for duplicates
            self._async_abort_entries_match(
                {CONF_HOST: self._host, CONF_PORT: self._port}
            )

        # Prepare updates
        updates = {CONF_HOST: self._host, CONF_PORT: self._port}
        if self._firmware_version:
            updates[CONF_FIRMWARE_VERSION] = self._firmware_version

        self._abort_if_unique_id_configured(updates=updates)

        return await self.async_step_auth()

    async def _validate_credentials(
        self, username: str, password: str, port: int, verify_ssl: bool
    ) -> tuple[Any | None, str | None]:
        """Validate credentials by attempting to connect to the device.

        Returns: (api_instance, error_string)
        - api_instance is None if validation failed
        - error_string is None if validation succeeded
        """
        if not self._host:
            return None, "missing_data"

        try:
            api = create_api_instance(
                device_type=self._device_model,
                host=self._host,
                username=username,
                password=password,
                port=port,
                verify_ssl=verify_ssl,
            )
            success, error_type = await self.hass.async_add_executor_job(
                attempt_login, api
            )
        except OSError:
            return None, "cannot_connect"

        if error_type == "ha_control_disabled":
            return None, "ha_control_disabled"

        if error_type == "offline":
            return None, "cannot_connect"

        if not success:
            return None, "invalid_auth"

        # Get MAC address from API after successful login
        if api.device_mac:
            self._mac = api.device_mac

        return api, None

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle authentication step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self._show_auth_form(errors)

        # Validate port number
        port_value = user_input.get(CONF_PORT, str(DEFAULT_PORT))
        is_valid, port = validate_port(port_value)
        if not is_valid:
            errors["port"] = "invalid_port"
            return self._show_auth_form(errors)

        # Validate credentials (username is fixed to "gdsha")
        verify_ssl = user_input.get(CONF_VERIFY_SSL, False)
        username = DEFAULT_USERNAME
        password = user_input[CONF_PASSWORD]

        api, validation_result = await self._validate_credentials(
            username, password, port, verify_ssl
        )

        if validation_result:
            errors["base"] = validation_result
            return self._show_auth_form(errors)

        # Set device name from API if not already set (e.g., from zeroconf)
        if not self._name and api:
            # Use device MAC or host as name for manual configuration
            self._name = f"{self._device_model.upper()} {self._mac or self._host}"

        # Set unique_id before creating entry (prefer MAC if available)
        if not self.unique_id:
            if self._mac:
                await self.async_set_unique_id(format_mac(self._mac))
            else:
                # Use _async_abort_entries_match to prevent duplicates
                # when MAC is not available (manual configuration)
                self._async_abort_entries_match(
                    {CONF_HOST: self._host, CONF_PORT: port}
                )

        # Create config entry (username is fixed, store password directly)
        return self.async_create_entry(
            title=self._name or "Grandstream Device",
            data={
                CONF_HOST: self._host,
                CONF_NAME: self._name,
                CONF_PORT: port,
                CONF_USERNAME: DEFAULT_USERNAME,
                CONF_PASSWORD: password,
                CONF_VERIFY_SSL: verify_ssl,
                CONF_DEVICE_MODEL: self._device_model,
                CONF_PRODUCT_MODEL: self._product_model,
                CONF_FIRMWARE_VERSION: self._firmware_version,
            },
        )

    def _show_auth_form(
        self,
        errors: dict[str, str],
    ) -> config_entries.ConfigFlowResult:
        """Show the authentication form."""
        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    # Username is fixed to "gdsha", only password is required
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_PORT, default=str(self._port)): cv.string,
                    vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                }
            ),
            errors=errors,
            description_placeholders={
                "host": self._host or "",
                "model": self._product_model or self._device_model.upper(),
            },
        )
