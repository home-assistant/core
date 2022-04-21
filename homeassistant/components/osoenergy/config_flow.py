"""Config Flow for OSO Energy."""
import logging

from apyosoenergyapi import OSOEnergy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import CONFIG_ENTRY_VERSION, DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)


class OSOEnergyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a OSO Energy config flow."""

    VERSION = CONFIG_ENTRY_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self.entry = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            # Get existing entry and abort if already setup
            self.entry = await self.async_set_unique_id(TITLE)
            if self.context["source"] != config_entries.SOURCE_REAUTH:
                self._abort_if_unique_id_configured()

            # Verify Subscription key
            valid = await self.test_credentials(user_input[CONF_API_KEY])
            if valid:
                if self.context["source"] == config_entries.SOURCE_REAUTH:
                    self.hass.config_entries.async_update_entry(
                        self.entry, title=TITLE, data=user_input
                    )
                    await self.hass.config_entries.async_reload(self.entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                return self.async_create_entry(title=TITLE, data=user_input)

            self._errors["base"] = "invalid_auth"

            return await self.show_config_form()

        return await self.show_config_form()

    async def show_config_form(self):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        data_schema = {vol.Required(CONF_API_KEY): str}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=self._errors,
        )

    async def test_credentials(self, subscription_key):
        """Return true if credentials is valid."""
        try:
            websession = aiohttp_client.async_get_clientsession(self.hass)
            client = OSOEnergy(subscription_key, websession)
            res = await client.get_devices()
            return res
        except Exception as inst:  # pylint: disable=broad-except
            _LOGGER.exception(inst)
        return False

    async def async_step_reauth(self, user_input=None):
        """Re Authenticate a user."""
        data = {CONF_API_KEY: user_input[CONF_API_KEY]}
        return await self.async_step_user(data)

    async def async_step_import(self, user_input=None):
        """Import user."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Hive options callback."""
        return OSOEnergyOptionsFlowHandler(config_entry)


class OSOEnergyOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for OSO Energy."""

    def __init__(self, config_entry):
        """Initialize Hive options flow."""
        self.osoenergy = None
        self.config_entry = config_entry
        self.interval = config_entry.options.get(CONF_SCAN_INTERVAL, 120)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user(user_input=user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self.osoenergy = self.hass.data[DOMAIN][self.config_entry.entry_id]
        errors = {}
        if user_input is not None:
            new_interval = user_input.get(CONF_SCAN_INTERVAL)
            await self.osoenergy.update_interval(new_interval)
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=self.interval): vol.All(
                    vol.Coerce(int), vol.Range(min=15)
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class UnknownOSOEnergyError(Exception):
    """Catch unknown OSO Energy error."""
