"""Config flow for Trello integration."""
from typing import Any

from trello import Member, Unauthorized
import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from . import TrelloAdapter
from .const import CONF_BOARD_IDS, CONF_USER_EMAIL, CONF_USER_ID, DOMAIN, LOGGER

USER_FORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the initial setup of a Trello integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data = {}
        self._trello_adapter: TrelloAdapter
        self._ids_boards: dict[str, dict[str, str]] = {}


    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prompt user for Trello API credentials."""
        errors = {}
        if user_input:
            self._trello_adapter = TrelloAdapter.from_data(user_input)
            try:
                member = await self.hass.async_add_executor_job(self._trello_adapter.get_member)
            except Unauthorized as ex:
                LOGGER.exception("Unauthorized", ex)
                errors={"base": "invalid_auth"}
            else:
                self._data = {
                    **user_input,
                    CONF_USER_ID: member.id,
                    CONF_USER_EMAIL: member.email,
                }

                await self.async_set_unique_id(member.id)
                self._abort_if_unique_id_configured()

                self._ids_boards = await self.hass.async_add_executor_job(self._trello_adapter.get_boards)
                return await self.async_step_boards()

        return self.async_show_form(
            step_id="user", data_schema=USER_FORM_SCHEMA,errors=errors, last_step=False
        )

    async def async_step_boards(self, user_input: dict[str, Any]) -> FlowResult:
        """Select desired boards to have card counts of per list.

        :param user_input: User's selected boards
        """
        if user_input:
            return self.async_create_entry(
                title=self.user_email, data=self._data, options=user_input
            )

        options = {key: value["name"] for key, value in self._ids_boards.items()}
        return self.async_show_form(
            step_id="boards",
            data_schema=vol.Schema({vol.Required(CONF_BOARD_IDS): cv.multi_select(options)}),
        )
