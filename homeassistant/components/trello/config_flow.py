"""Config flow for Trello integration."""

from typing import Any

from trello import TrelloClient, Unauthorized
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.helpers import config_validation as cv

from .const import CONF_BOARD_IDS, CONF_USER_EMAIL, CONF_USER_ID, DOMAIN, LOGGER

USER_FORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the initial setup of a Trello integration."""

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}
        self._trello_client: TrelloClient
        self._ids_boards: dict[str, dict[str, str]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user for Trello API credentials."""
        errors = {}
        if user_input:
            self._trello_client = TrelloClient(
                api_key=user_input["api_key"], api_secret=user_input["api_token"]
            )
            try:
                member = await self.hass.async_add_executor_job(
                    self._trello_client.get_member, "me"
                )
            except Unauthorized as ex:
                LOGGER.exception("Unauthorized: %s", ex)
                errors = {"base": "invalid_auth"}
            else:
                self._data = {
                    **user_input,
                    CONF_USER_ID: member.id,
                    CONF_USER_EMAIL: member.email,
                }

                await self.async_set_unique_id(member.id)
                self._abort_if_unique_id_configured()

                self._ids_boards = await self.hass.async_add_executor_job(
                    self._get_boards
                )
                options = {
                    key: value["name"] for key, value in self._ids_boards.items()
                }
                schema = vol.Schema(
                    {vol.Required(CONF_BOARD_IDS): cv.multi_select(options)}
                )
                return self.async_show_form(
                    step_id="boards",
                    data_schema=schema,
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_FORM_SCHEMA, errors=errors, last_step=False
        )

    async def async_step_boards(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Select desired boards to have card counts of per list.

        :param user_input: User's selected boards
        """
        return self.async_create_entry(
            title=self._data[CONF_USER_EMAIL], data=self._data, options=user_input
        )

    def _get_boards(self) -> dict[str, dict[str, str]]:
        """Get all user's boards."""
        return {
            board.id: {"id": board.id, "name": board.name}
            for board in self._trello_client.list_boards(board_filter="open")
        }
