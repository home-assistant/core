"""Config flow for the VegeHub integration."""

import logging
from typing import Any

from vegehub import VegeHub
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VegeHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VegeHub integration."""

    def __init__(self) -> None:
        """Initialize the VegeHub config flow."""
        self._hub: VegeHub | None = None
        self._hostname: str = ""
        self._properties: dict = {}
        self._config_url: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial confirmation step with no inputs."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if CONF_IP_ADDRESS in user_input and self._hub is None:
                # When the user has input the IP manually, we need to gather more information
                # from the Hub before we can continue setup.
                self._hub = VegeHub(user_input[CONF_IP_ADDRESS])

                try:
                    await self._hub.retrieve_mac_address(retries=2)
                except ConnectionError:
                    _LOGGER.error("Failed to connect to %s", self._hub.ip_address)
                    errors["base"] = "cannot_connect"

                if len(self._hub.mac_address) <= 0:
                    _LOGGER.error(
                        "Failed to get MAC address for %s", self._hub.ip_address
                    )
                    errors["base"] = "cannot_connect"

                self._async_abort_entries_match({CONF_IP_ADDRESS: self._hub.ip_address})

                # Set the unique ID for the manual configuration
                await self.async_set_unique_id(self._hub.mac_address)
                # Abort if this device is already configured
                self._abort_if_unique_id_configured()

                self._hostname = self._hub.ip_address
                self._config_url = f"http://{self._hub.ip_address}"

            if self._hub is not None:
                if len(self._hub.ip_address) <= 0 or len(self._hub.mac_address) <= 0:
                    _LOGGER.error("Missing IP address or MAC address for device")
                    errors["base"] = "missing_data"
                else:
                    try:
                        # Attempt communication with the Hub before creating the entry to
                        # make sure it's awake and ready to be set up.
                        await self._hub.retrieve_mac_address()
                    except ConnectionError:
                        _LOGGER.error("Failed to connect to %s", self._hub.ip_address)
                        errors["base"] = "cannot_connect"
                    except TimeoutError:
                        _LOGGER.error(
                            "Timed out trying to connect to %s", self._hub.ip_address
                        )
                        errors["base"] = "timeout_connect"

                if len(errors) == 0:
                    info_data: dict[str, Any] = {}

                    info_data[CONF_MAC] = self._hub.mac_address
                    info_data[CONF_IP_ADDRESS] = self._hub.ip_address
                    info_data[CONF_HOST] = self._hostname
                    info_data[ATTR_SW_VERSION] = self._properties.get("version")
                    info_data[ATTR_CONFIGURATION_URL] = self._config_url

                    # Create the config entry for the new device
                    return self.async_create_entry(
                        title=f"{self._hostname}", data=info_data
                    )

        if self._hub is None:
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

        # If we already have an IP address, we can just ask the user if they want to continue
        return self.async_show_form(step_id="user", errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # Extract the IP address from the zeroconf discovery info
        device_ip = discovery_info.host

        self._hostname = discovery_info.hostname.removesuffix(".local.")
        self._config_url = (
            f"http://{discovery_info.hostname[:-1]}:{discovery_info.port}"
        )
        self._properties = discovery_info.properties

        self._async_abort_entries_match({CONF_IP_ADDRESS: discovery_info.host})

        self._hub = VegeHub(device_ip)

        try:
            await self._hub.retrieve_mac_address(retries=2)
        except ConnectionError:
            _LOGGER.error("Failed to connect to %s", self._hub.ip_address)
            return self.async_abort(reason="cannot_connect")

        if len(self._hub.mac_address) <= 0:
            _LOGGER.error("Failed to get MAC address for %s", device_ip)
            return self.async_abort(reason="cannot_connect")

        # Check if this device already exists
        await self.async_set_unique_id(self._hub.mac_address)
        self._abort_if_unique_id_configured()

        self.context.update(
            {
                "title_placeholders": {"host": self._hostname + " (" + device_ip + ")"},
                "configuration_url": (self._config_url),
            }
        )

        # If the device is new, allow the user to continue setup
        return await self.async_step_user()
