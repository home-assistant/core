"""Config Flow for OSO Energy."""
from collections.abc import Mapping
import logging
from typing import Any

from apyosoenergyapi import OSOEnergy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import CONFIG_ENTRY_VERSION, DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)


class OSOEnergyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a OSO Energy config flow."""

    VERSION = CONFIG_ENTRY_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}
        self.entry: ConfigEntry | None = None

    async def async_step_user(self, user_input=None) -> FlowResult:
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
                if (
                    self.context["source"] == config_entries.SOURCE_REAUTH
                    and self.entry
                ):
                    self.hass.config_entries.async_update_entry(
                        self.entry, title=TITLE, data=user_input
                    )
                    await self.hass.config_entries.async_reload(self.entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                return self.async_create_entry(title=TITLE, data=user_input)

            self._errors["base"] = "invalid_auth"

        return await self.show_config_form()

    async def show_config_form(self):  # pylint: disable=unused-argument
        """Show the configuration form to edit API key."""
        data_schema = {vol.Required(CONF_API_KEY): str}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=self._errors,
        )

    async def test_credentials(self, subscription_key: str) -> bool:
        """Return true if credentials is valid."""
        try:
            websession = aiohttp_client.async_get_clientsession(self.hass)
            client = OSOEnergy(subscription_key, websession)
            res = await client.get_devices()
            return bool(res)
        except Exception as inst:  # pylint: disable=broad-except
            _LOGGER.exception(inst)
        return False

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Re Authenticate a user."""
        data = {CONF_API_KEY: user_input[CONF_API_KEY]}
        return await self.async_step_user(data)
