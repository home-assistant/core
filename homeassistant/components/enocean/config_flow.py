"""Config flows for the ENOcean integration."""
from enum import Enum

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import CONN_CLASS_ASSUMED
from homeassistant.const import CONF_DEVICE

from . import EnOceanDongle
from .const import DOMAIN, ERROR_INVALID_DONGLE_PATH


class DongleSetupStates(Enum):
    """The statuses of the enocean dongle configuration state machine."""

    SELECT_AUTO = 1
    SELECT_MANUAL = 2
    VALIDATE = 3
    CREATE_ENTRY = 4


class EnOceanFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the enOcean config flows."""

    VERSION = 1
    MANUAL_PATH_VALUE = "Custom path"
    CONNECTION_CLASS = CONN_CLASS_ASSUMED

    def __init__(self):
        """Initialize the EnOcean config flow."""
        self.dongle_path = None
        self.discovery_info = None

    async def async_step_import(self, data=None):
        """Import a yaml configuration."""
        return self.async_create_entry(title="EnOcean", data=data)

    async def async_step_user(self, user_input=None):
        """Handle an EnOcean config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return await self.async_step_detect()
        elif user_input[CONF_DEVICE] == self.MANUAL_PATH_VALUE:
            return await self.async_step_manual(user_input)
        else:
            return await self.async_step_validate(user_input)

    async def async_step_detect(self, user_input=None):
        """Propose a list of detected dongles."""
        bridges = await self.hass.async_add_executor_job(EnOceanDongle.detect)
        if len(bridges) == 0:
            return await self.async_step_manual(user_input)

        bridges.append(self.MANUAL_PATH_VALUE)
        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(bridges)}),
        )

    async def async_step_manual(self, user_input=None, errors=None):
        """Request manual USB dongle path."""
        default_value = None
        if user_input is not None and user_input[CONF_DEVICE] != self.MANUAL_PATH_VALUE:
            default_value = user_input[CONF_DEVICE]
        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE, default=default_value): str}
            ),
            errors=errors,
        )

    async def async_step_validate(self, user_input):
        """Validate the provided path."""
        dongle_path = user_input[CONF_DEVICE]

        if dongle_path == self.MANUAL_PATH_VALUE:
            return await self.async_step_manual(user_input)

        path_is_valid = await self.hass.async_add_executor_job(
            EnOceanDongle.validate_path, dongle_path
        )
        if not path_is_valid:
            errors = {CONF_DEVICE: ERROR_INVALID_DONGLE_PATH}
            return await self.async_step_manual(user_input, errors)

        return await self.async_step_create_entry(user_input)

    async def async_step_create_entry(self, user_input):
        """Create an entry for the provided configuration."""
        return self.async_create_entry(title="EnOcean", data=user_input)
