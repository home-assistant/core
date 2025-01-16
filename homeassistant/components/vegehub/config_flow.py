"""Config flow for the VegeHub integration."""

import logging
from typing import Any

from vegehub import VegeHub
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.webhook import (
    async_generate_id as webhook_generate_id,
    async_generate_url as webhook_generate_url,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_WEBHOOK_ID,
)
from homeassistant.util.network import is_ip_address

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VegeHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VegeHub integration."""

    def __init__(self) -> None:
        """Initialize the VegeHub config flow."""
        self._hub: VegeHub | None = None
        self._hostname: str = ""
        self._discovered: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not is_ip_address(user_input[CONF_IP_ADDRESS]):
                # User-supplied IP address is invalid.
                _LOGGER.error("Invalid IP address")
                errors["base"] = "invalid_ip"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_IP_ADDRESS, default=user_input[CONF_IP_ADDRESS]
                            ): str,
                        }
                    ),
                    errors=errors,
                )

            self._hub = VegeHub(user_input[CONF_IP_ADDRESS])

            self._hostname = self._hub.ip_address

            # Proceed to create the config entry
            return await self._async_create_entry()

        # Show the form to allow the user to manually enter the IP address
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS): str,
                }
            ),
            errors={},
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # Extract the IP address from the zeroconf discovery info
        device_ip = discovery_info.host

        self._async_abort_entries_match({CONF_IP_ADDRESS: device_ip})

        self._hostname = discovery_info.hostname.removesuffix(".local.")
        config_url = f"http://{discovery_info.hostname[:-1]}:{discovery_info.port}"

        self._hub = VegeHub(device_ip)

        try:
            await self._hub.retrieve_mac_address(retries=2)
        except ConnectionError:
            _LOGGER.error("Failed to connect to %s", self._hub.ip_address)
            return self.async_abort(reason="cannot_connect")
        except TimeoutError:
            _LOGGER.error("Timed out trying to connect to %s", self._hub.ip_address)
            return self.async_abort(reason="timeout_connect")

        if len(self._hub.mac_address) <= 0:
            _LOGGER.error("Failed to get MAC address for %s", device_ip)
            return self.async_abort(reason="cannot_connect")

        # Check if this device already exists
        await self.async_set_unique_id(self._hub.mac_address)
        self._abort_if_unique_id_configured()

        self.context.update(
            {
                "title_placeholders": {"host": self._hostname + " (" + device_ip + ")"},
                "configuration_url": (config_url),
            }
        )

        # If the device is new, allow the user to continue setup
        return self.async_show_form(step_id="zeroconf_confirm")

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation for a discovered device."""
        if user_input is not None:
            return await self._async_create_entry()

        # Show the confirmation form
        return self.async_show_form(step_id="zeroconf_confirm")

    async def async_step_error_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle error in setup process and allow retry."""
        if user_input is not None:
            return await self._async_create_entry()

        # Show the confirmation form
        return self.async_show_form(step_id="error_retry")

    async def _async_create_entry(self) -> ConfigFlowResult:
        """Create a config entry for the device."""
        errors: dict[str, str] = {}
        webhook_id = webhook_generate_id()
        webhook_url = webhook_generate_url(
            self.hass,
            webhook_id,
            allow_external=False,
            allow_ip=True,
        )

        # This should be impossible, but mypy demands that we check for None
        if self._hub is None:
            return self.async_abort(reason="unknown_error")

        # Send the webhook address to the hub as its server target.
        # This step should only happen when the config flow happens, not
        # in the async_setup_entry, which happens again during boot.
        try:
            await self._hub.setup("", webhook_url, retries=1)
        except ConnectionError:
            _LOGGER.error("Failed to connect to %s", self._hub.ip_address)
            errors["base"] = "cannot_connect"
        except TimeoutError:
            _LOGGER.error("Timed out trying to connect to %s", self._hub.ip_address)
            errors["base"] = "timeout_connect"

        if len(self._hub.mac_address) <= 0:
            _LOGGER.error("Failed to get MAC address for %s", self._hub.ip_address)
            errors["base"] = "cannot_connect"

        if len(errors) > 0:
            return self.async_show_form(step_id="error_retry", errors=errors)

        self._discovered = {
            CONF_IP_ADDRESS: self._hub.ip_address,
            CONF_HOST: self._hostname,
            CONF_MAC: self._hub.mac_address,
        }

        # Check if this device already exists
        await self.async_set_unique_id(self._hub.mac_address)
        self._abort_if_unique_id_configured()

        # Save Hub info to be used later when defining the VegeHub object
        info_data = {
            **self._discovered,
            CONF_DEVICE: self._hub.info,
            CONF_WEBHOOK_ID: webhook_id,
        }

        # Create the config entry for the new device
        return self.async_create_entry(title=f"{self._hostname}", data=info_data)
