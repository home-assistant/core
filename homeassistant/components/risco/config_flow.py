"""Config flow for Risco integration."""
import logging

from pyrisco import CannotConnectError, RiscoAPI, UnauthorizedError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    CONF_HA_STATES_TO_RISCO,
    CONF_RISCO_STATES_TO_HA,
    DEFAULT_OPTIONS,
    DOMAIN,
    RISCO_STATES,
)

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PIN): str,
    }
)
HA_STATES = [
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
]


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    risco = RiscoAPI(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PIN])

    try:
        await risco.login(async_get_clientsession(hass))
    finally:
        await risco.close()

    return {"title": risco.site_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Risco."""

    VERSION = 1

    @staticmethod
    @core.callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return RiscoOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except UnauthorizedError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class RiscoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a Risco options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry
        self._data = {**DEFAULT_OPTIONS, **config_entry.options}

    def _options_schema(self):
        return vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=self._data[CONF_SCAN_INTERVAL]
                ): int,
                vol.Required(
                    CONF_CODE_ARM_REQUIRED, default=self._data[CONF_CODE_ARM_REQUIRED]
                ): bool,
                vol.Required(
                    CONF_CODE_DISARM_REQUIRED,
                    default=self._data[CONF_CODE_DISARM_REQUIRED],
                ): bool,
            }
        )

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            self._data = {**self._data, **user_input}
            return await self.async_step_risco_to_ha()

        return self.async_show_form(step_id="init", data_schema=self._options_schema())

    async def async_step_risco_to_ha(self, user_input=None):
        """Map Risco states to HA states."""
        if user_input is not None:
            self._data[CONF_RISCO_STATES_TO_HA] = user_input
            return await self.async_step_ha_to_risco()

        risco_to_ha = self._data[CONF_RISCO_STATES_TO_HA]
        options = vol.Schema(
            {
                vol.Required(risco_state, default=risco_to_ha[risco_state]): vol.In(
                    HA_STATES
                )
                for risco_state in RISCO_STATES
            }
        )

        return self.async_show_form(step_id="risco_to_ha", data_schema=options)

    async def async_step_ha_to_risco(self, user_input=None):
        """Map HA states to Risco states."""
        if user_input is not None:
            self._data[CONF_HA_STATES_TO_RISCO] = user_input
            return self.async_create_entry(title="", data=self._data)

        options = {}
        risco_to_ha = self._data[CONF_RISCO_STATES_TO_HA]
        # we iterate over HA_STATES, instead of set(self._risco_to_ha.values())
        # to ensure a consistent order
        for ha_state in HA_STATES:
            if ha_state not in risco_to_ha.values():
                continue

            values = [
                risco_state
                for risco_state in RISCO_STATES
                if risco_to_ha[risco_state] == ha_state
            ]
            current = self._data[CONF_HA_STATES_TO_RISCO].get(ha_state)
            if current not in values:
                current = values[0]
            options[vol.Required(ha_state, default=current)] = vol.In(values)

        return self.async_show_form(
            step_id="ha_to_risco", data_schema=vol.Schema(options)
        )
