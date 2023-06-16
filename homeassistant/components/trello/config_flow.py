"""Config flow for Trello integration."""
from typing import Any

from trello import Member, Unauthorized
import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from . import TrelloAdapter
from .const import (
    CONF_API_TOKEN,
    CONF_BOARD_IDS,
    CONF_BOARDS,
    CONF_USER_EMAIL,
    CONF_USER_ID,
    DOMAIN,
    LOGGER,
)

CREDS_FORM_SCHEMA = vol.Schema(
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
        self.api_key: str = ""
        self.api_token: str = ""
        self.user_email: str = ""
        self.user_id: str = ""
        self.ids_boards: dict[str, dict[str, str]] = {}
        self.trello_adapter: TrelloAdapter

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prompt user for Trello API credentials."""
        return await self._show_creds_form()

    async def async_step_creds(self, user_input: dict[str, Any]) -> FlowResult:
        """Re-prompt for creds if invalid. Otherwise, prompt user for boards.

        :param user_input: api_key and api_token.
        """
        self.api_key = user_input[CONF_API_KEY]
        self.api_token = user_input[CONF_API_TOKEN]
        self.trello_adapter = TrelloAdapter.from_creds(
            user_input[CONF_API_KEY], user_input[CONF_API_TOKEN]
        )

        try:
            member = await self._get_current_member()
        except Unauthorized as ex:
            return await self._show_error_creds_form(ex)

        self.user_id = member.id
        self.user_email = member.email
        self.ids_boards = await self._fetch_all_boards()

        return await self._show_board_form(self.ids_boards)

    async def async_step_boards(self, user_input: dict[str, Any]) -> FlowResult:
        """Select desired boards to have card counts of per list.

        :param user_input: User's selected boards
        """
        boards: dict[str, dict] = await self._get_boards_lists(
            user_input[CONF_BOARD_IDS]
        )

        await self.async_set_unique_id(self.user_id)
        self._abort_if_unique_id_configured()

        config_data: dict[str, str] = self._get_config_data()
        config_options = {CONF_BOARDS: boards}

        return self.async_create_entry(
            title=self.user_email, data=config_data, options=config_options
        )

    def _get_config_data(self) -> dict[str, str]:
        return {
            CONF_API_KEY: self.api_key,
            CONF_API_TOKEN: self.api_token,
            CONF_USER_ID: self.user_id,
            CONF_USER_EMAIL: self.user_email,
        }

    async def _show_creds_form(self) -> FlowResult:
        return self.async_show_form(
            step_id="creds", data_schema=CREDS_FORM_SCHEMA, last_step=False
        )

    async def _show_board_form(
        self, ids_boards: dict[str, dict[str, str]]
    ) -> FlowResult:
        return self.async_show_form(
            step_id="boards",
            data_schema=_get_board_select_schema(ids_boards),
        )

    async def _show_error_creds_form(self, ex: Unauthorized) -> FlowResult:
        LOGGER.error("Unauthorized: %s)", ex)
        return self.async_show_form(
            step_id="creds",
            data_schema=CREDS_FORM_SCHEMA,
            errors={"base": "invalid_auth"},
            last_step=False,
        )

    async def _fetch_all_boards(self) -> dict[str, dict[str, str]]:
        return await self.hass.async_add_executor_job(self.trello_adapter.get_boards)

    async def _get_boards_lists(self, board_ids: list[str]) -> dict[str, dict]:
        return await self.hass.async_add_executor_job(
            self.trello_adapter.get_board_lists, self.ids_boards, board_ids
        )

    async def _get_current_member(self) -> Member:
        return await self.hass.async_add_executor_job(self.trello_adapter.get_member)


def _get_board_select_schema(boards: dict[str, dict]) -> Schema:
    options = {key: value["name"] for key, value in boards.items()}
    return vol.Schema({vol.Required(CONF_BOARD_IDS): cv.multi_select(options)})
