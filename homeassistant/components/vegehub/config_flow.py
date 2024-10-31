"""Config flow for the VegeHub integration."""

import logging
import socket
from typing import Any

import aiohttp
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
        self.device_ip: str = ""
        self.mac_addr: str = ""
        self.hostname: str = ""
        self.sw_ver: str = ""
        self.properties: dict = {}
        self.config_url: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial confirmation step with no inputs."""
        errors = {}

        if user_input is not None:
            if "ip_address" in user_input and len(self.device_ip) <= 0:
                # When the user has input the IP manually, we need to gather more information first
                self.device_ip = str(user_input.get("ip_address"))
                _LOGGER.info("User input of %s", self.device_ip)

                self.mac_addr = await self._get_device_mac(self.device_ip)

                if len(self.mac_addr) <= 0:
                    _LOGGER.error("Failed to get device config from %s", self.device_ip)
                    return self.async_abort(reason="cannot_connect")

                try:
                    # Check to see if this MAC address is already in the list.
                    entry = list(ip_dict.keys())[
                        list(ip_dict.values()).index(self.mac_addr)
                    ]
                    if entry:
                        ip_dict.pop(entry)
                except ValueError:
                    pass

                # Set the unique ID for the manual configuration
                await self.async_set_unique_id(self.mac_addr)
                # Abort if this device is already configured
                self._abort_if_unique_id_configured()

                self.hostname = self.device_ip
                self.config_url = f"http://{self.device_ip}"

            if len(self.device_ip) > 0:
                _LOGGER.info("Setting up hub %s", self.device_ip)
                try:
                    # Fetch current config from the device
                    config_data = await self._get_device_config(self.device_ip)

                    # Modify the config (for example, update the server_url with hostname.local)
                    modified_config = self._modify_device_config(config_data)

                    # Send the modified config back to the device
                    await self._set_device_config(self.device_ip, modified_config)

                    info_data = await self._get_device_info(self.device_ip)

                    info_data["mac_address"] = self.mac_addr
                    info_data["ip_addr"] = self.device_ip
                    info_data["hostname"] = self.hostname
                    info_data["sw_ver"] = self.sw_ver
                    info_data["properties"] = self.properties
                    info_data["config_url"] = self.config_url

                    # Create a task to ask the hub for an update when it can, so that we have initial data
                    self.hass.async_create_task(self._ask_for_update(self.device_ip))

                    # Create the config entry for the new device
                    return self.async_create_entry(
                        title=f"{self.hostname}", data=info_data
                    )

                except Exception as e:
                    _LOGGER.error("Failed to update device config: %s", e)
                    errors["base"] = "cannot_connect"
                    raise
            else:
                _LOGGER.error("No IP address for device")
                errors["base"] = "cannot_connect"

        if len(self.device_ip) <= 0:
            # Show the form to allow the user to manually enter the IP address
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "ip_address"
                        ): str,  # Use Home Assistant's IP validator if needed
                    }
                ),
                errors={},
            )

        # If we already have an IP address, we can just ask the user if they want to continue
        return self.async_show_form(step_id="user", errors=errors)

    async def _get_device_info(self, ip_address):
        """Fetch the current configuration from the device."""
        url = f"http://{ip_address}/api/info/get"

        payload = {"hub": []}

        # Snick - We can add in a call here to grab the names for all the sensors and actuators. That way we can fill those in as defaults, and the user can change them to whatever they want.

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, json=payload) as response,
        ):
            if response.status != 200:
                _LOGGER.error(
                    "Failed to get config from %s: HTTP %s", url, response.status
                )

            # Parse the response JSON
            info_data = await response.json()
            _LOGGER.info("Received info from %s", ip_address)
            return info_data

    async def _get_device_config(self, ip_address):
        """Fetch the current configuration from the device."""
        url = f"http://{ip_address}/api/config/get"

        payload = {"hub": [], "api_key": []}

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, json=payload) as response,
        ):
            if response.status != 200:
                _LOGGER.error(
                    "Failed to get config from %s: HTTP %s", url, response.status
                )

            # Parse the response JSON
            return await response.json()

    def _modify_device_config(self, config_data):
        """Modify the device config by adding or updating the API key."""
        error = False

        # Assuming the API key should be added to the 'hub' section, modify as necessary
        if "api_key" in config_data:
            config_data["api_key"] = self.mac_addr
        else:
            error = True

        # Retrieve the Home Assistant hostname
        hostname = socket.gethostname()  # Get the local hostname
        server_url = f"http://{hostname}.local:8123/api/vegehub/update"  # Use the ".local" domain for local mDNS resolution

        # Modify the server_url in the returned JSON
        if "hub" in config_data:
            config_data["hub"]["server_url"] = server_url
            config_data["hub"]["server_type"] = 3
        else:
            error = True

        if error:
            return False
        return config_data

    async def _set_device_config(self, ip_address, config_data):
        """Send the modified configuration back to the device."""
        url = f"http://{ip_address}/api/config/set"

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, json=config_data) as response,
        ):
            if response.status != 200:
                _LOGGER.error(
                    "Failed to set config at %s: HTTP %s", url, response.status
                )

    async def _ask_for_update(self, ip_address):
        """Ask the device to send in an update so we have initial values."""
        url = f"http://{ip_address}/api/update/send"

        async with aiohttp.ClientSession() as session, session.get(url) as response:
            if response.status != 200:
                _LOGGER.error(
                    "Failed to ask for update from %s: HTTP %s", url, response.status
                )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # Extract the IP address from the zeroconf discovery info
        self.device_ip = discovery_info.host

        # _LOGGER.info(f"Here's a test I should have done earlier: {discovery_info}")
        # discovery_info contains:

        #     (ip_address=ZeroconfIPv4Address('192.168.0.104'), ip_addresses=[ZeroconfIPv4Address('192.168.0.104'),
        #     ZeroconfIPv6Address('fe80::fab3:b7ff:fe21:a620')], port=80, hostname='Vege_A6_20.local.',
        #     type='_vege._tcp.local.', name='Vege_A6_20._vege._tcp.local.',
        #     properties={'version': '5.1.1', 'type': 'hub', 'receiver': '/api/vsens/data_in', 'sensors': '1',
        #     'actuators': '0', 'sens_1': 'Sensor1', 'power_mode': '0'})

        have_mac = False

        if self.device_ip in ip_dict:
            have_mac = True

        self.hostname = discovery_info.hostname.removesuffix(".local.")
        self.sw_ver = discovery_info.properties["version"]
        self.config_url = f"http://{discovery_info.hostname[:-1]}:{discovery_info.port}"
        self.properties = discovery_info.properties

        if not have_mac:
            # Now request the /api/config_get endpoint to get the device config
            self.mac_addr = await self._get_device_mac(self.device_ip)

            if len(self.mac_addr) <= 0:
                _LOGGER.error("Failed to get device config from %s", self.device_ip)
                return self.async_abort(reason="cannot_connect")

            try:
                # Check to see if this MAC address is already in the list.
                entry = list(ip_dict.keys())[
                    list(ip_dict.values()).index(self.mac_addr)
                ]
                if entry:  # If it's already in the list, then it is connected to another IP address. Remove that entry.
                    ip_dict.pop(entry)
                    _LOGGER.info(
                        "Zeroconf found a new IP address for %s at %s",
                        self.mac_addr,
                        self.device_ip,
                    )
            except ValueError:
                _LOGGER.info("Zeroconf found new device at %s", self.device_ip)

            # Add a new entry to the list of IP:MAC pairs that we have seen
            ip_dict[self.device_ip] = self.mac_addr
        else:
            self.mac_addr = ip_dict[self.device_ip]

        # Check if this device already exists
        await self.async_set_unique_id(self.mac_addr)
        self._abort_if_unique_id_configured()

        self.context.update(
            {
                "title_placeholders": {"host": self.hostname},
                "configuration_url": (self.config_url),
            }
        )

        # If the device is new, allow the user to continue setup
        return await self.async_step_user()

    async def _get_device_mac(self, ip_address):
        """Fetch the MAC address by sending a POST request to the device's /api/config_get."""
        url = f"http://{ip_address}/api/info/get"

        # Prepare the JSON payload for the POST request
        payload = {"wifi": []}

        # Use aiohttp to send the POST request with the JSON body
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, json=payload) as response,
        ):
            if response.status != 200:
                _LOGGER.error(
                    "Failed to get config from %s: HTTP %s", url, response.status
                )

            # Parse the JSON response
            config_data = await response.json()
            mac_address = config_data.get("wifi", {}).get("mac_addr")
            if not mac_address:
                _LOGGER.error(
                    "MAC address not found in the config response from %s", ip_address
                )
                return ""
            simplified_mac_address = mac_address.replace(":", "").lower()
            _LOGGER.info("%s MAC address: %s", ip_address, mac_address)
            return simplified_mac_address
        return ""

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
            # Define the schema for the options that the user can modify
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
            if current_duration <= 0:
                current_duration = 600

            options_schema.update(
                {vol.Required("user_act_duration", default=current_duration): int}
            )

        # Show the form to the user with the current options
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema)
        )
