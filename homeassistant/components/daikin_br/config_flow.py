"""Config flow for the Daikin smart AC."""

from __future__ import annotations

import base64
import binascii
import logging
from typing import Any

from pyiotdevice import async_get_thing_info, get_hostname
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

# from zeroconf import ServiceInfo
from .const import COMMAND_SUFFIX, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Schema for manual device IP entry when discovery_info is absent
MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required("device_ip"): str,
        vol.Required("device_name"): str,
        vol.Required(CONF_API_KEY): str,
    }
)

# Schema for the discovered device flow (when discovery_info exists)
DISCOVERED_SCHEMA = vol.Schema(
    {
        vol.Required("device_name"): str,
        vol.Required(CONF_API_KEY): str,
    }
)


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Daikin Climate."""

    DOMAIN = DOMAIN
    VERSION = 1

    # Add a new attribute for discovery info.
    discovery_info: dict | None = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle discovery via zeroconf."""
        _LOGGER.debug("Discovered device via zeroconf: %s", discovery_info)

        # Extract hostname (remove ".local" suffix), host/ip and apn
        # hostname = discovery_info.hostname.rstrip(".local.")
        hostname = discovery_info.hostname
        if discovery_info.hostname.endswith(".local."):
            hostname = discovery_info.hostname.removesuffix(".local.")
        elif discovery_info.hostname.endswith(".local"):
            hostname = discovery_info.hostname.removesuffix(".local")

        host = str(discovery_info.ip_address)
        apn = discovery_info.properties.get("apn")

        if not hostname:
            return self.async_abort(reason="unknown_device")

        # Check if device is already configured
        # pylint: disable=no-else-return
        existing_entry = self._async_find_existing_entry(apn)
        if existing_entry:
            if existing_entry.data.get("host") != host:
                _LOGGER.info(
                    "Device IP has changed from %s to %s; Updating config entry",
                    existing_entry.data.get("host"),
                    host,
                )
                return self.async_update_reload_and_abort(
                    existing_entry,
                    # data={**existing_entry.data, "host": host},
                    data_updates={"host": host},
                    reason="device_ip_updated",
                )
            return self.async_abort(reason="already_configured")

        _LOGGER.info("Discovered Daikin device: %s at %s", hostname, host)

        # Set the unique ID for this flow
        await self.async_set_unique_id(apn)

        # Abort if a config entry with the same unique ID already exists
        self._abort_if_unique_id_configured()

        # Override context to force UI to show meaningful title
        self.context["title_placeholders"] = {
            "name": hostname,
        }

        # Store discovery data for use in the next step
        self.discovery_info = {
            "host_name": hostname,  # Store hostname without .local
            "host": host,  # Store IP address
            "device_apn": apn,
        }

        # Prompt user for device_key entry
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle user configuration step."""
        # discovery_info = self.context.get("discovery_info", {})
        discovery_info = self.discovery_info or {}

        errors = {}

        # If no discovery info is available
        # we prompt the user to input the device IP address.
        # pylint: disable=no-else-return
        if not discovery_info:
            return await self.async_step_manual(user_input)
        # Discovery info exists. Use discovered details.
        default_host_name = discovery_info.get("host_name", "")
        default_host = discovery_info.get("host", "")  # Discovered device IP address
        ip_address = default_host
        device_apn = discovery_info.get("device_apn", "")

        if user_input is not None:
            _LOGGER.debug("User input received")
            device_name = user_input.get("device_name", "").strip()
            api_key = user_input.get(CONF_API_KEY, "").strip()

            # Check if the user entered the device name
            if not device_name:
                errors["device_name"] = "required"

            # Check if the user entered the device key
            if not api_key:
                errors[CONF_API_KEY] = "required"

            # Step 1: Validate Base64 key before proceeding
            elif not self._is_valid_base64(api_key):
                _LOGGER.error("Invalid device key format")
                errors[CONF_API_KEY] = "invalid_key"

            # Step 2: Validate key by attempting decryption
            elif not await async_get_thing_info(ip_address, api_key, "acstatus"):
                _LOGGER.error("Invalid device key or host not reachable")
                errors[CONF_API_KEY] = "cannot_connect"

            else:
                # Create the config entry with the discovered and user-provided data
                return self.async_create_entry(
                    title=(f"{user_input['device_name']} (SSID: {default_host_name})"),
                    data={
                        "device_name": user_input["device_name"],
                        CONF_API_KEY: api_key,
                        "host": default_host,
                        "device_apn": device_apn,
                        "device_ssid": default_host_name,
                        "command_suffix": COMMAND_SUFFIX,
                    },
                )

        # If we reach this point
        # it means the form has not been submitted yet or there was an error
        return self.async_show_form(
            step_id="user",
            data_schema=DISCOVERED_SCHEMA,
            errors=errors,
            description_placeholders={
                "hostname": default_host_name,
                "host": default_host,
            },
        )

    async def async_step_manual(
        self, user_input: Any | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle manual entry step when no device is discovered."""
        errors = {}

        if user_input is not None:
            _LOGGER.debug("Manual flow: Received user input")
            ip_address = user_input.get("device_ip", "").strip()
            device_name = user_input.get("device_name", "").strip()
            api_key = user_input.get(CONF_API_KEY, "").strip()

            if not ip_address:
                errors["device_ip"] = "required"
            if not device_name:
                errors["device_name"] = "required"

            if not api_key:
                errors[CONF_API_KEY] = "required"

            # Step 1: Validate Base64 key before proceeding
            elif not self._is_valid_base64(api_key):
                _LOGGER.error("Invalid device key format")
                errors[CONF_API_KEY] = "invalid_key"

            # Step 2: Validate key by attempting decryption
            elif not await async_get_thing_info(ip_address, api_key, "acstatus"):
                _LOGGER.error("Invalid device key or host not reachable")
                errors[CONF_API_KEY] = "cannot_connect"
            else:
                # Call get_thing_info to try to fetch device details
                device_info = await async_get_thing_info(ip_address, api_key, "device")
                if not device_info or "apn" not in device_info:
                    errors["device_ip"] = "cannot_connect"
                else:
                    # Retrieve device APN from response
                    device_apn = device_info.get("apn")
                    _LOGGER.debug("device_apn: %s", device_apn)
                    # Use the provided IP as the host and host_name for subsequent steps
                    default_host = ip_address
                    # Get the hostname using device_apn
                    default_host_name = get_hostname(device_apn)
                    _LOGGER.debug("default_host_name: %s", default_host_name)

                    # Set the unique ID for this flow
                    await self.async_set_unique_id(device_apn)
                    # Abort if a config entry with the same unique ID already exists
                    self._abort_if_unique_id_configured()

                    # Check if device is already configured
                    existing_entry = self._async_find_existing_entry(device_apn)
                    if existing_entry:
                        return self.async_abort(reason="already_configured")

                    # Create the config entry with all data
                    return self.async_create_entry(
                        title=(
                            f"{user_input['device_name']} (SSID: {default_host_name})"
                        ),
                        data={
                            "device_name": user_input["device_name"],
                            CONF_API_KEY: api_key,
                            "host": default_host,
                            "device_apn": device_apn,
                            "device_ssid": default_host_name,
                            "command_suffix": COMMAND_SUFFIX,
                        },
                    )

        # Show form to enter device IP address, device name and device key
        return self.async_show_form(
            step_id="manual",
            data_schema=MANUAL_SCHEMA,
            errors=errors,
            description_placeholders={"host": "Enter the device IP address"},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration flow to update the device key.

        This flow is triggered when a user wants to reconfigure the device key
        without creating a new config entry.
        """
        # Get the existing config entry that is being reconfigured.
        entry = self._get_reconfigure_entry()
        old_data = entry.data
        default_host_name = old_data.get("device_ssid", "")
        default_host = old_data.get("host", "")
        ip_address = default_host
        device_apn = old_data.get("device_apn", "")

        errors = {}

        if user_input is not None:
            _LOGGER.debug("Reconfigure user input received")
            new_api_key = user_input.get(CONF_API_KEY, "").strip()

            if not new_api_key:
                errors[CONF_API_KEY] = "required"
            elif not self._is_valid_base64(new_api_key):
                errors[CONF_API_KEY] = "invalid_key"
            elif not await async_get_thing_info(ip_address, new_api_key, "device"):
                errors[CONF_API_KEY] = "cannot_connect"

            if not errors:
                # Ensure that the unique ID remains unchanged.
                await self.async_set_unique_id(device_apn)
                self._abort_if_unique_id_mismatch()
                # Create a new data dict that updates the API key.
                new_data = {**old_data, CONF_API_KEY: new_api_key}
                return self.async_update_reload_and_abort(
                    entry, data_updates=new_data, reason="reconfigure_successful"
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "hostname": default_host_name,
                "host": default_host,
            },
        )

    def _is_valid_base64(self, key):
        """Check if the provided key is a valid base64 string."""
        try:
            if not key or len(key) % 4 not in (0, 2, 3):
                return False
            base64.b64decode(key, validate=True)
        # pylint: disable=broad-exception-caught
        # except Exception:
        except binascii.Error:
            return False
        else:
            return True

    def _async_find_existing_entry(self, device_apn):
        """Check if the device is already configured."""
        for entry in self._async_current_entries():
            if entry.data.get("device_apn") == device_apn:
                return entry
        return None
