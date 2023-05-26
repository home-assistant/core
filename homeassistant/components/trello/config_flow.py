"""Config flow for Trello integration."""

from trello import TrelloClient, Unauthorized
import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, device_registry as dr

from . import TrelloAdapter
from .const import (
    CONF_API_TOKEN,
    CONF_OPTIONS_BOARDS,
    CONF_USER_EMAIL,
    CONF_USER_ID,
    DOMAIN,
    LOGGER,
    USER_INPUT_BOARD_IDS,
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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Prompt user for Trello API credentials.

        :param user_input: None initially or users api_key and api_token.
        :return:
        """
        if _is_first_config_form(user_input):
            return await self._show_creds_form()

        self.api_key = user_input[CONF_API_KEY]
        self.api_token = user_input[CONF_API_TOKEN]
        self.trello_adapter = _create_trello_adapter(
            user_input[CONF_API_KEY], user_input[CONF_API_TOKEN]
        )

        try:
            member = await self._get_current_member()
        except Unauthorized as ex:
            return await self._show_error_creds_form(ex)

        self.user_id = member.id
        self.user_email = member.email
        self.ids_boards = await self._fetch_all_boards()

        return await self._show_board_form()

    async def async_step_finish(self, user_input=None) -> FlowResult:
        """Select desired boards to have card counts of per list.

        :param user_input: User's selected boards
        """
        boards: dict[str, dict] = await self._get_boards_lists(
            user_input[USER_INPUT_BOARD_IDS]
        )

        await self.async_set_unique_id(self.user_id)
        self._abort_if_unique_id_configured()

        config_data: dict[str, str] = self._get_config_data()
        config_options = {CONF_OPTIONS_BOARDS: boards}

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

    async def _show_creds_form(self):
        return self.async_show_form(
            step_id="user", data_schema=CREDS_FORM_SCHEMA, last_step=False
        )

    async def _show_board_form(self):
        return self.async_show_form(
            step_id="finish",
            data_schema=_get_board_select_schema(self.ids_boards),
            last_step=True,
        )

    async def _show_error_creds_form(self, ex: Unauthorized):
        LOGGER.error("Unauthorized: %s)", ex)
        return self.async_show_form(
            step_id="user",
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

    async def _get_current_member(self):
        return await self.hass.async_add_executor_job(self.trello_adapter.get_member)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Trello."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_options = config_entry.options
        self.trello_adapter = _create_trello_adapter(
            config_entry.data[CONF_API_KEY], config_entry.data[CONF_API_TOKEN]
        )

        self.ids_boards: dict[str, dict[str, str]] = {}

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Select desired boards to have card counts of per list.

        :param user_input: None initially or the user's selected boards
        """
        configured_board_ids = self.config_options[CONF_OPTIONS_BOARDS].keys()

        if _is_first_config_form(user_input):
            self.ids_boards = await self._fetch_all_boards()

            return await self._show_board_form(configured_board_ids)

        await self._remove_deselected_boards(
            configured_board_ids, user_input[USER_INPUT_BOARD_IDS]
        )

        user_selected_boards = await self._get_boards_lists(
            user_input[USER_INPUT_BOARD_IDS]
        )

        new_config_options = {CONF_OPTIONS_BOARDS: user_selected_boards}
        return self.async_create_entry(data=new_config_options)

    async def _show_board_form(self, configured_board_ids):
        return self.async_show_form(
            step_id="init",
            data_schema=_get_board_select_schema(
                self.ids_boards, list(configured_board_ids)
            ),
        )

    async def _remove_deselected_boards(
        self, configured_board_ids, user_selected_board_ids
    ):
        for configured_board_id in configured_board_ids:
            if configured_board_id not in user_selected_board_ids:
                dev_reg = dr.async_get(self.hass)
                device = dev_reg.async_get_device(
                    identifiers={(DOMAIN, configured_board_id)}
                )
                dev_reg.async_remove_device(device.id)

    async def _fetch_all_boards(self) -> dict[str, dict[str, str]]:
        return await self.hass.async_add_executor_job(self.trello_adapter.get_boards)

    async def _get_boards_lists(self, board_ids: list[str]) -> dict[str, dict]:
        return await self.hass.async_add_executor_job(
            self.trello_adapter.get_board_lists, self.ids_boards, board_ids
        )


def _create_trello_adapter(api_key: str, api_token: str) -> TrelloAdapter:
    return TrelloAdapter(TrelloClient(api_key=api_key, api_secret=api_token))


def _get_board_select_schema(boards: dict[str, dict], default=None) -> Schema:
    if default is None:
        default = []
    options = {key: value["name"] for key, value in boards.items()}
    return vol.Schema(
        {vol.Required(USER_INPUT_BOARD_IDS, default=default): cv.multi_select(options)}
    )


def _is_first_config_form(user_input) -> bool:
    return user_input is None
