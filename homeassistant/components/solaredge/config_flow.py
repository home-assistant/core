"""Config flow for the SolarEdge platform."""
from requests.exceptions import ConnectTimeout, HTTPError
import solaredge
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import CONF_SITE_ID, DEFAULT_NAME, DOMAIN


@callback
def solaredge_entries(hass: HomeAssistant):
    """Return the site_ids for the domain."""
    return {
        (entry.data[CONF_SITE_ID])
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


class SolarEdgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors = {}

    def _site_in_configuration_exists(self, site_id) -> bool:
        """Return True if site_id exists in configuration."""
        if site_id in solaredge_entries(self.hass):
            return True
        return False

    def _check_site(self, site_id, api_key) -> bool:
        """Check if we can connect to the soleredge api service."""
        api = solaredge.Solaredge(api_key)
        try:
            response = api.get_details(site_id)
        except (ConnectTimeout, HTTPError):
            self._errors[CONF_SITE_ID] = "could_not_connect"
            return False
        try:
            if response["details"]["status"].lower() != "active":
                self._errors[CONF_SITE_ID] = "site_not_active"
                return False
        except KeyError:
            self._errors[CONF_SITE_ID] = "api_failure"
            return False
        return True

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
            if self._site_in_configuration_exists(user_input[CONF_SITE_ID]):
                self._errors[CONF_SITE_ID] = "site_exists"
            else:
                site = user_input[CONF_SITE_ID]
                api = user_input[CONF_API_KEY]
                can_connect = await self.hass.async_add_executor_job(
                    self._check_site, site, api
                )
                if can_connect:
                    return self.async_create_entry(
                        title=name, data={CONF_SITE_ID: site, CONF_API_KEY: api}
                    )

        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_SITE_ID] = ""
            user_input[CONF_API_KEY] = ""

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(CONF_SITE_ID, default=user_input[CONF_SITE_ID]): str,
                    vol.Required(CONF_API_KEY, default=user_input[CONF_API_KEY]): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        if self._site_in_configuration_exists(user_input[CONF_SITE_ID]):
            return self.async_abort(reason="site_exists")
        return await self.async_step_user(user_input)
