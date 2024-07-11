"""Config Flow for PlayStation 4."""

from collections import OrderedDict

from pyps4_2ndscreen.errors import CredentialTimeout
from pyps4_2ndscreen.helpers import Helper
from pyps4_2ndscreen.media_art import COUNTRIES
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_REGION,
    CONF_TOKEN,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import location

from .const import (
    CONFIG_ENTRY_VERSION,
    COUNTRYCODE_NAMES,
    DEFAULT_ALIAS,
    DEFAULT_NAME,
    DOMAIN,
)

CONF_MODE = "Config Mode"
CONF_AUTO = "Auto Discover"
CONF_MANUAL = "Manual Entry"

LOCAL_UDP_PORT = 1988
UDP_PORT = 987
TCP_PORT = 997
PORT_MSG = {UDP_PORT: "port_987_bind_error", TCP_PORT: "port_997_bind_error"}

PIN_LENGTH = 8


class PlayStation4FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a PlayStation 4 config flow."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self):
        """Initialize the config flow."""
        self.helper = Helper()
        self.creds = None
        self.name = None
        self.host = None
        self.region = None
        self.pin = None
        self.m_device = None
        self.location = None
        self.device_list = []

    async def async_step_user(self, user_input=None):
        """Handle a user config flow."""
        # Check if able to bind to ports: UDP 987, TCP 997.
        ports = PORT_MSG.keys()
        failed = await self.hass.async_add_executor_job(self.helper.port_bind, ports)
        if failed in ports:
            reason = PORT_MSG[failed]
            return self.async_abort(reason=reason)
        return await self.async_step_creds()

    async def async_step_creds(self, user_input=None):
        """Return PS4 credentials from 2nd Screen App."""
        errors = {}
        if user_input is not None:
            try:
                self.creds = await self.hass.async_add_executor_job(
                    self.helper.get_creds, DEFAULT_ALIAS
                )
                if self.creds is not None:
                    return await self.async_step_mode()
                return self.async_abort(reason="credential_error")
            except CredentialTimeout:
                errors["base"] = "credential_timeout"

        return self.async_show_form(step_id="creds", errors=errors)

    async def async_step_mode(self, user_input=None):
        """Prompt for mode."""
        errors = {}
        mode = [CONF_AUTO, CONF_MANUAL]

        if user_input is not None:
            if user_input[CONF_MODE] == CONF_MANUAL:
                try:
                    if device := user_input[CONF_IP_ADDRESS]:
                        self.m_device = device
                except KeyError:
                    errors[CONF_IP_ADDRESS] = "no_ipaddress"
            if not errors:
                return await self.async_step_link()

        mode_schema = OrderedDict()
        mode_schema[vol.Required(CONF_MODE, default=CONF_AUTO)] = vol.In(list(mode))
        mode_schema[vol.Optional(CONF_IP_ADDRESS)] = str

        return self.async_show_form(
            step_id="mode", data_schema=vol.Schema(mode_schema), errors=errors
        )

    async def async_step_link(self, user_input=None):
        """Prompt user input. Create or edit entry."""
        regions = sorted(COUNTRIES.keys())
        default_region = None
        errors = {}

        if user_input is None:
            # Search for device.
            # If LOCAL_UDP_PORT cannot be used, a random port will be selected.
            devices = await self.hass.async_add_executor_job(
                self.helper.has_devices, self.m_device, LOCAL_UDP_PORT
            )

            # Abort if can't find device.
            if not devices:
                return self.async_abort(reason="no_devices_found")

            self.device_list = [device["host-ip"] for device in devices]

            # Check that devices found aren't configured per account.
            entries = self._async_current_entries()
            if entries:
                # Retrieve device data from all entries if creds match.
                conf_devices = [
                    device
                    for entry in entries
                    if self.creds == entry.data[CONF_TOKEN]
                    for device in entry.data["devices"]
                ]

                # Remove configured device from search list.
                for c_device in conf_devices:
                    if c_device["host"] in self.device_list:
                        # Remove configured device from search list.
                        self.device_list.remove(c_device["host"])

                # If list is empty then all devices are configured.
                if not self.device_list:
                    return self.async_abort(reason="already_configured")

        # Login to PS4 with user data.
        if user_input is not None:
            self.region = user_input[CONF_REGION]
            self.name = user_input[CONF_NAME]
            # Assume pin had leading zeros, before coercing to int.
            self.pin = str(user_input[CONF_CODE]).zfill(PIN_LENGTH)
            self.host = user_input[CONF_IP_ADDRESS]

            is_ready, is_login = await self.hass.async_add_executor_job(
                self.helper.link,
                self.host,
                self.creds,
                self.pin,
                DEFAULT_ALIAS,
                LOCAL_UDP_PORT,
            )

            if is_ready is False:
                errors["base"] = "cannot_connect"
            elif is_login is False:
                errors["base"] = "login_failed"
            else:
                device = {
                    CONF_HOST: self.host,
                    CONF_NAME: self.name,
                    CONF_REGION: self.region,
                }

                # Create entry.
                return self.async_create_entry(
                    title="PlayStation 4",
                    data={CONF_TOKEN: self.creds, "devices": [device]},
                )

        # Try to find region automatically.
        if not self.location:
            self.location = await location.async_detect_location_info(
                async_get_clientsession(self.hass)
            )
        if self.location:
            country = COUNTRYCODE_NAMES.get(self.location.country_code)
            if country in COUNTRIES:
                default_region = country

        # Show User Input form.
        link_schema = OrderedDict()
        link_schema[vol.Required(CONF_IP_ADDRESS)] = vol.In(list(self.device_list))
        link_schema[vol.Required(CONF_REGION, default=default_region)] = vol.In(
            list(regions)
        )
        link_schema[vol.Required(CONF_CODE)] = vol.All(
            vol.Strip, vol.Length(max=PIN_LENGTH), vol.Coerce(int)
        )
        link_schema[vol.Required(CONF_NAME, default=DEFAULT_NAME)] = str

        return self.async_show_form(
            step_id="link", data_schema=vol.Schema(link_schema), errors=errors
        )
