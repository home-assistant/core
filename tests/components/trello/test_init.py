"""Test the trello config flow."""
from unittest.mock import Mock

from homeassistant.components.trello import TrelloAdapter
from homeassistant.core import HomeAssistant

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


async def test_flow_trello_adapter_get_member(hass: HomeAssistant) -> None:
    """Test trello adapter returns the client libs authed member."""
    mock_client = Mock()
    mock_client.get_member.return_value = "a_member"

    adapter = TrelloAdapter(mock_client)

    actual = adapter.get_member()

    assert actual == "a_member"


async def test_flow_trello_adapter_get_boards(hass: HomeAssistant) -> None:
    """Test trello adapter retrieving the users boards."""
    mock_client = Mock()
    mock_board = Mock(id=BOARD_ID)
    mock_board.name = "a_board_name"
    mock_board_2 = Mock(id="a_board_id_2")
    mock_board_2.name = "a_board_name_2"
    mock_client.list_boards.return_value = [mock_board, mock_board_2]

    adapter = TrelloAdapter(mock_client)

    actual = adapter.get_boards()

    assert actual == {
        BOARD_ID: {"id": BOARD_ID, "name": "a_board_name"},
        "a_board_id_2": {"id": "a_board_id_2", "name": "a_board_name_2"},
    }
