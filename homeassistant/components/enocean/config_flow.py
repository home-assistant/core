"""Config flows for the ENOcean integration."""
from enum import Enum
from os import path

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE

from . import EnOceanDongle
from .const import CONNECTION_ENOCEAN, DOMAIN, ERROR_INVALID_DONGLE_PATH, LOGGER


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
    CONNECTION_CLASS = CONNECTION_ENOCEAN

    def __init__(self):
        """Initialize the EnOcean config flow."""
        self.dongle_path = None
        self.discovery_info = None

    async def async_step_init(self, user_input=None):
        """Needed in order to not require re-translation of strings."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle an EnOcean config flow start.

        This flow will be used when the user sets up the ENOcean integration.
        It uses a state machine to walk through the different steps of the
        configuration.
        """
        enocean_configured = DOMAIN in self.hass.config.components
        if enocean_configured:
            return self.async_abort(reason="dongle_already_configured")

        if user_input is None:
            config_state = DongleSetupStates.SELECT_AUTO
        elif user_input[CONF_DEVICE] == self.MANUAL_PATH_VALUE:
            config_state = DongleSetupStates.SELECT_MANUAL
        else:
            config_state = DongleSetupStates.VALIDATE

        return await self.set_dongle_setup_state(config_state, user_input)

    async def set_dongle_setup_state(self, new_state, user_input=None, errors={}):
        """Change the current state of the dongle setup state machine (re-entrant method)."""
        if new_state == DongleSetupStates.SELECT_MANUAL:
            LOGGER.debug(f"Config step: select manual with errors={errors}")
            default_value = None
            if (
                user_input is not None
                and CONF_DEVICE in user_input
                and user_input[CONF_DEVICE] != self.MANUAL_PATH_VALUE
            ):
                default_value = user_input[CONF_DEVICE]
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {vol.Required(CONF_DEVICE, default=default_value): str}
                ),
                errors=errors,
            )

        elif new_state == DongleSetupStates.SELECT_AUTO:
            LOGGER.debug("Config step: select auto")
            bridges = EnOceanDongle.detect()
            if len(bridges) == 0:
                return await self.set_dongle_setup_state(
                    DongleSetupStates.SELECT_MANUAL, user_input
                )

            bridges.append(self.MANUAL_PATH_VALUE)
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(bridges)}),
            )

        elif new_state == DongleSetupStates.VALIDATE:
            LOGGER.debug("Config step: validate")
            dongle_path = user_input[CONF_DEVICE]
            if path.exists(dongle_path) and not path.isdir(dongle_path):
                return await self.set_dongle_setup_state(
                    DongleSetupStates.CREATE_ENTRY, user_input
                )
            else:
                errors = {CONF_DEVICE: ERROR_INVALID_DONGLE_PATH}
                return await self.set_dongle_setup_state(
                    DongleSetupStates.SELECT_MANUAL, user_input, errors
                )

        elif new_state == DongleSetupStates.CREATE_ENTRY:
            LOGGER.debug("Config step: create entry")
            await self.async_set_unique_id(user_input[CONF_DEVICE])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="EnOcean", data=user_input)
