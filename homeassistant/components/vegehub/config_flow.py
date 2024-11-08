"""Config flow for the VegeHub integration."""

import logging
import socket
from typing import Any

from vegehub import VegeHub
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback

from .const import DOMAIN, OPTION_DATA_TYPE_CHOICES

_LOGGER = logging.getLogger(__name__)


ip_dict: dict[str, str] = {}


class VegeHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VegeHub integration."""

    VERSION = 1

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
        errors = {}

        if user_input is not None:
            if "ip_address" in user_input and self._hub is None:
                # When the user has input the IP manually, we need to gather more information
                # from the Hub before we can continue setup.
                self._hub = VegeHub(str(user_input.get("ip_address")))

                await self._hub.retrieve_mac_address()

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
                    pass

                # Set the unique ID for the manual configuration
                await self.async_set_unique_id(self._hub.mac_address)
                # Abort if this device is already configured
                self._abort_if_unique_id_configured()

                self._hostname = self._hub.ip_address
                self._config_url = f"http://{self._hub.ip_address}"

            if self._hub is not None:
                try:
                    hostname = socket.gethostname()  # Get the local hostname
                    # Use the ".local" domain for local mDNS resolution
                    await self._hub.setup(
                        self._hub.mac_address,
                        f"http://{hostname}.local:8123/api/vegehub/update",
                    )

                    info_data = self._hub.info

                    info_data["mac_address"] = self._hub.mac_address
                    info_data["ip_addr"] = self._hub.ip_address
                    info_data["hostname"] = self._hostname
                    info_data["sw_ver"] = self._properties.get("version")
                    info_data["config_url"] = self._config_url

                    # Create a task to ask the hub for an update when it can,
                    # so that we have initial data
                    self.hass.async_create_task(self._hub.request_update())

                    # Create the config entry for the new device
                    return self.async_create_entry(
                        title=f"{self._hostname}", data=info_data
                    )

                except Exception as e:
                    _LOGGER.error("Failed to update device config: %s", e)
                    errors["base"] = "cannot_connect"
                    raise
            else:
                _LOGGER.error("No IP address for device")
                errors["base"] = "cannot_connect"

        if self._hub is None:
            # Show the form to allow the user to manually enter the IP address
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("ip_address"): str,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow handler for this integration."""
        return VegehubOptionsFlowHandler(config_entry)


class VegehubOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for VegeHub."""

    def __init__(self, config_entry) -> None:
        """Initialize VegeHub options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options for VegeHub."""
        if user_input is not None:
            # Update the config entry options with the new user input
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=user_input
            )

            # Trigger a reload of the config entry to apply the new options
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            # Process the user inputs and update the config entry options
            return self.async_create_entry(title="", data=user_input)

        num_sensors = self.config_entry.data.get("hub", {}).get("num_channels")
        num_actuators = self.config_entry.data.get("hub", {}).get("num_actuators")

        options_schema: dict[Any, Any] = {}

        if num_sensors > 0:
            # Define data_type fields depending on the number of sensors this hub has
            options_schema.update(
                {
                    vol.Required(
                        f"data_type_{i + 1}",
                        default=self.config_entry.options.get(
                            f"data_type_{i + 1}", OPTION_DATA_TYPE_CHOICES[0]
                        ),
                    ): vol.In(OPTION_DATA_TYPE_CHOICES)
                    for i in range(num_sensors)
                }
            )

        # Check to see if there are actuators. If there are, add the duration field.
        if num_actuators > 0:
            # Get the current duration value from the config entry
            current_duration = self.config_entry.options.get("user_act_duration", 0)
            # If the current duration is invalid, make it default to 600 seconds
            if current_duration <= 0:
                current_duration = 600

            options_schema.update(
                {vol.Required("user_act_duration", default=current_duration): int}
            )

        # Show the form to the user with the available options
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema)
        )
