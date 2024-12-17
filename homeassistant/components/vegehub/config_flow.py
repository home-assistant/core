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
    ATTR_CONFIGURATION_URL,
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_WEBHOOK_ID,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


ip_dict: dict[str, str] = {}


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
                    await self._hub.retrieve_mac_address()
                except ConnectionError:
                    _LOGGER.error(
                        "Failed to get MAC address for %s", self._hub.ip_address
                    )

                if len(self._hub.mac_address) <= 0:
                    _LOGGER.error(
                        "Failed to get device config from %s", self._hub.ip_address
                    )
                    return self.async_abort(reason="cannot_connect")

                try:
                    # Check to see if this MAC address is already in the list.
                    entry = list(ip_dict.keys())[
                        list(ip_dict.values()).index(self._hub.mac_address)
                    ]
                    # If the mac address is on the list, pop it so we can give it a new IP
                    if entry:
                        ip_dict.pop(entry)
                except ValueError:
                    # If the MAC address is not in the list, a ValueError will be thrown,
                    # which just means that we don't need to remove it from the list.
                    pass

                # Add a new entry to the list of IP:MAC pairs that we have seen
                ip_dict[self._hub.ip_address] = self._hub.mac_address

                # Set the unique ID for the manual configuration
                await self.async_set_unique_id(self._hub.mac_address)
                # Abort if this device is already configured
                self._abort_if_unique_id_configured()

                self._hostname = self._hub.ip_address
                self._config_url = f"http://{self._hub.ip_address}"

            if self._hub is not None:
                webhook_id = webhook_generate_id()
                webhook_url = webhook_generate_url(
                    self.hass,
                    webhook_id,
                    allow_external=False,
                    allow_ip=True,
                )

                # Send the webhook address to the hub as its server target
                await self._hub.setup(
                    "",
                    webhook_url,
                )

                info_data = self._hub.info

                info_data[CONF_MAC] = self._hub.mac_address
                info_data[CONF_IP_ADDRESS] = self._hub.ip_address
                info_data[CONF_HOST] = self._hostname
                info_data[ATTR_SW_VERSION] = self._properties.get("version")
                info_data[ATTR_CONFIGURATION_URL] = self._config_url
                info_data[CONF_WEBHOOK_ID] = webhook_id

                # Create a task to ask the hub for an update when it can,
                # so that we have initial data
                self.hass.async_create_task(self._hub.request_update())

                # Create the config entry for the new device
                return self.async_create_entry(
                    title=f"{self._hostname}", data=info_data
                )

            _LOGGER.error("No IP address for device")
            errors["base"] = "cannot_connect"

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

        # Keep track of which IP addresses have already had their MAC addresses
        # discovered. This allows us to skip the MAC address retrieval for devices
        # that don't need it. This stops us from waking up a hub every time we see
        # it come on-line.
        have_mac = False
        if device_ip in ip_dict:
            have_mac = True

        self._hostname = discovery_info.hostname.removesuffix(".local.")
        self._config_url = (
            f"http://{discovery_info.hostname[:-1]}:{discovery_info.port}"
        )
        self._properties = discovery_info.properties

        if not have_mac:
            self._hub = VegeHub(device_ip)

            await self._hub.retrieve_mac_address()

            if len(self._hub.mac_address) <= 0:
                _LOGGER.error("Failed to get device config from %s", device_ip)
                return self.async_abort(reason="cannot_connect")

            try:
                # Check to see if this MAC address is already in the list.
                entry = list(ip_dict.keys())[
                    list(ip_dict.values()).index(self._hub.mac_address)
                ]
                if entry:
                    # If it's already in the list, then it is connected to another
                    # IP address. Remove that entry.
                    ip_dict.pop(entry)
            except ValueError:
                _LOGGER.info("Zeroconf found new device at %s", device_ip)

            # Add a new entry to the list of IP:MAC pairs that we have seen
            ip_dict[device_ip] = self._hub.mac_address
        else:
            self._hub = VegeHub(device_ip, mac_address=ip_dict[device_ip])

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
