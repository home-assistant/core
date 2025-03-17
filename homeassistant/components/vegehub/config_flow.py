"""Config flow for the VegeHub integration."""

import logging
from typing import Any

from vegehub import VegeHub
import voluptuous as vol

from homeassistant import config_entries
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
from homeassistant.helpers.service_info import zeroconf
from homeassistant.util.network import is_ip_address

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VegeHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VegeHub integration."""

    _hub: VegeHub
    _hostname: str
    webhook_id: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not is_ip_address(user_input[CONF_IP_ADDRESS]):
                # User-supplied IP address is invalid.
                errors["base"] = "invalid_ip"

            if not errors:
                self._hub = VegeHub(user_input[CONF_IP_ADDRESS])
                self._hostname = self._hub.ip_address
                errors = await self._setup_device()
                if not errors:
                    # Proceed to create the config entry
                    return await self._create_entry()

        # Show the form to allow the user to manually enter the IP address
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS): str,
                }
            ),
            errors=errors,
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

        # Create a VegeHub object to interact with the device
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
        self._abort_if_unique_id_configured(updates={CONF_HOST: device_ip})

        # Add title and configuration URL to the context so that the device discovery
        # tile has the correct title, and a "Visit Device" link available.
        self.context.update(
            {
                "title_placeholders": {"host": self._hostname + " (" + device_ip + ")"},
                "configuration_url": (config_url),
            }
        )

        # If the device is new, allow the user to continue setup
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation for a discovered device."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._setup_device()
            if not errors:
                return await self._create_entry()

        # Show the confirmation form
        self._set_confirm_only()
        return self.async_show_form(step_id="zeroconf_confirm", errors=errors)

    async def _setup_device(self) -> dict[str, str]:
        """Set up the VegeHub device."""
        errors: dict[str, str] = {}
        self.webhook_id = webhook_generate_id()
        webhook_url = webhook_generate_url(
            self.hass,
            self.webhook_id,
            allow_external=False,
            allow_ip=True,
        )

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

        if not self._hub.mac_address:
            _LOGGER.error("Failed to get MAC address for %s", self._hub.ip_address)
            errors["base"] = "cannot_connect"

        return errors

    async def _create_entry(self) -> ConfigFlowResult:
        """Create a config entry for the device."""

        # Check if this device already exists
        await self.async_set_unique_id(self._hub.mac_address)
        self._abort_if_unique_id_configured()

        # Save Hub info to be used later when defining the VegeHub object
        info_data = {
            CONF_IP_ADDRESS: self._hub.ip_address,
            CONF_HOST: self._hostname,
            CONF_MAC: self._hub.mac_address,
            CONF_DEVICE: self._hub.info,
            CONF_WEBHOOK_ID: self.webhook_id,
        }

        # Create the config entry for the new device
        return self.async_create_entry(title=f"{self._hostname}", data=info_data)
