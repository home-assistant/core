"""Config flow for Yeelight integration."""
import logging

import voluptuous as vol
import yeelight

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_DISCOVERY, CONF_IP_ADDRESS, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from . import (
    CONF_DEVICE,
    CONF_MODE_MUSIC,
    CONF_MODEL,
    CONF_NIGHTLIGHT_SWITCH,
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
)
from . import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

TYPE_DISCOVERY = "Discovery"
TYPE_MANUAL = "Manual"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yeelight."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        if config_entry.data[CONF_DISCOVERY]:
            return DiscoveryOptionsFlowHandler(config_entry)
        return ManualOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        self._capabilities = None
        self._ipaddr = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            if user_input[CONF_TYPE] == TYPE_DISCOVERY:
                return await self.async_step_discovery_setup()
            return await self.async_step_manual()

        for entry in self._async_current_entries():
            if entry.data[CONF_DISCOVERY]:  # Only one discovery entry allowed
                return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_TYPE): vol.In([TYPE_DISCOVERY, TYPE_MANUAL])}
            ),
        )

    async def async_step_discovery_setup(self, user_input=None):
        """Handle discovery setup."""
        if user_input is not None:
            # Check if there is at least one device
            # Run 3 times as packets can get lost
            for _ in range(3):
                devices = await self.hass.async_add_executor_job(
                    yeelight.discover_bulbs
                )
                if len(devices) > 0:
                    return self.async_create_entry(
                        title="Discovery", data={CONF_DISCOVERY: True},
                    )
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(step_id="discovery_setup")

    async def async_step_manual(self, user_input=None):
        """Handle manually setup."""
        errors = {}

        if user_input is not None:
            self._ipaddr = user_input[CONF_IP_ADDRESS]
            if self._async_ip_already_configured():
                return self.async_abort(reason="already_configured")
            try:
                return await self._async_setup(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IP_ADDRESS, default=user_input.get(CONF_IP_ADDRESS, "")
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input=None):
        """Handle import step."""
        self._ipaddr = user_input[CONF_IP_ADDRESS]
        if self._async_ip_already_configured():
            return self.async_abort(reason="already_configured")
        try:
            if CONF_NIGHTLIGHT_SWITCH_TYPE in user_input:
                user_input[CONF_NIGHTLIGHT_SWITCH] = (
                    user_input.pop(CONF_NIGHTLIGHT_SWITCH_TYPE)
                    == NIGHTLIGHT_SWITCH_TYPE_LIGHT
                )
            return await self._async_setup(user_input)
        except CannotConnect:
            _LOGGER.error("Failed to import %s: cannot connect", self._ipaddr)
            return self.async_abort(reason="cannot_connect")

    async def _async_setup(self, user_input=None, is_import=False):
        """Set up with options."""
        bulb = yeelight.Bulb(self._ipaddr)
        try:
            capabilities = await self.hass.async_add_executor_job(bulb.get_capabilities)
            if capabilities is None:  # timeout
                _LOGGER.error(
                    "Failed to get capabilities from %s: timeout", self._ipaddr
                )
                raise CannotConnect
        except OSError as err:
            _LOGGER.error("Failed to get capabilities from %s: %s", self._ipaddr, err)
            raise CannotConnect
        _LOGGER.debug("Get capabilities: %s", capabilities)
        self._capabilities = capabilities
        await self.async_set_unique_id(capabilities["id"])
        self._abort_if_unique_id_configured()

        user_input[CONF_DISCOVERY] = False
        return self.async_create_entry(
            title=user_input[CONF_IP_ADDRESS], data=user_input
        )

    @callback
    def _async_ip_already_configured(self):
        """See if we already have an endpoint matching user input."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_IP_ADDRESS) == self._ipaddr:
                return True
        return False


@callback
def _async_options_data_schema(options: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_MODEL, default=options[CONF_MODEL],): str,
            vol.Required(
                CONF_TRANSITION, default=options[CONF_TRANSITION],
            ): cv.positive_int,
            vol.Required(CONF_MODE_MUSIC, default=options[CONF_MODE_MUSIC],): bool,
            vol.Required(
                CONF_SAVE_ON_CHANGE, default=options[CONF_SAVE_ON_CHANGE],
            ): bool,
            vol.Required(
                CONF_NIGHTLIGHT_SWITCH, default=options[CONF_NIGHTLIGHT_SWITCH],
            ): bool,
        }
    )


class ManualOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for manually set Yeelight."""

    def __init__(self, config_entry):
        """Initialize the option flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        return await self.async_step_options()

    async def async_step_options(self, user_input=None):
        """Handle the step to change options."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._config_entry.data[CONF_IP_ADDRESS], data=user_input
            )

        return self.async_show_form(
            step_id="options",
            data_schema=_async_options_data_schema(self._config_entry.options),
        )


class DiscoveryOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for discovery Yeelight."""

    def __init__(self, config_entry):
        """Initialize the option flow."""
        self._config_entry = config_entry
        self._devices = None
        self._picked_device = None

    async def async_step_init(self, user_input=None):
        """Handle option flow initialization."""
        device_registry = await dr.async_get_registry(self.hass)
        self._devices = {}
        for unique_id in self._config_entry.options:
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, unique_id)}, connections={}
            )
            name = device.name_by_user or device.name
            self._devices[f"{name} ({unique_id})"] = unique_id
        return await self.async_step_device()

    async def async_step_device(self, user_input=None):
        """Handle step to pick a device."""
        if user_input is not None:
            self._picked_device = self._devices[user_input[CONF_DEVICE]]
            return await self.async_step_options()
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE): vol.In(self._devices.keys())}
            ),
        )

    async def async_step_options(self, user_input=None):
        """Handle step to change options."""
        if user_input is not None:
            options = {**self._config_entry.options}
            options[self._picked_device] = user_input
            return self.async_create_entry(title="Discovery", data=options,)

        options = self._config_entry.options[self._picked_device]
        return self.async_show_form(
            step_id="options", data_schema=_async_options_data_schema(options)
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
