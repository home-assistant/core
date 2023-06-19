"""Test the trello config flow."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from trello import Unauthorized

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.trello.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import BOARD_LISTS

API_KEY = "an_api_key"
API_TOKEN = "an_api_token"
USER_ID = "a_user_id"
EMAIL_ADDR = "an_email"

BOARD_ID = "a_board_id"

BOARD_ID_LISTS = {
    BOARD_ID: BOARD_LISTS,
}

USER_INPUT_CREDS = {"api_key": API_KEY, "api_token": API_TOKEN}


class MockAdapter:
    """Mock TrelloAdapter."""

    def __init__(self, trello_client) -> None:
        """Init mock TrelloAdapter."""

    @classmethod
    def from_creds(cls, api_key: str, api_token: str):
        """Init mock TrelloAdapter."""
        return cls(None)

    def get_member(self):
        """Mock member object."""
        return SimpleNamespace(id=USER_ID, email=EMAIL_ADDR)

    def get_boards(self):
        """Mock board dict."""
        return {BOARD_ID: {"id": BOARD_ID, "name": "a_board_name"}}

    def get_board_lists(self, id_boards, selected_board_ids):
        """Mock board dict."""
        return BOARD_ID_LISTS


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test full user setup flow."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.trello.config_flow.TrelloAdapter",
        new=MockAdapter,
    ), patch(
        "homeassistant.components.trello.async_setup_entry",
        return_value=True,
    ):
        creds_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"], user_input=USER_INPUT_CREDS
        )

        board_selection_result = await hass.config_entries.flow.async_configure(
            creds_result["flow_id"],
            user_input={"board_ids": [BOARD_ID]},
        )

    assert init_result["type"] == FlowResultType.FORM
    assert init_result["step_id"] == "creds"
    assert init_result["last_step"] is False

    assert creds_result["step_id"] == "boards"
    assert creds_result["data_schema"].schema["board_ids"].options == {
        BOARD_ID: "a_board_name"
    }

    assert board_selection_result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert board_selection_result["data"] == {
        "api_key": API_KEY,
        "api_token": API_TOKEN,
        "user_id": USER_ID,
        "user_email": EMAIL_ADDR,
    }
    assert board_selection_result["options"] == {"board_ids": [BOARD_ID]}
    assert board_selection_result["result"].unique_id == USER_ID
    assert board_selection_result["result"].title == EMAIL_ADDR


async def test_flow_user_unauthorized(hass: HomeAssistant) -> None:
    """Test user setup flow when user enters invalid creds."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.trello.config_flow.TrelloAdapter.get_member",
        side_effect=Unauthorized("", Mock(status=123)),
    ), patch(
        "homeassistant.components.trello.async_setup_entry",
        return_value=True,
    ):
        creds_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input=USER_INPUT_CREDS,
        )

    assert creds_result["type"] == FlowResultType.FORM
    assert creds_result["step_id"] == "creds"
    assert creds_result["errors"] == {"base": "invalid_auth"}
    assert creds_result["last_step"] is False
