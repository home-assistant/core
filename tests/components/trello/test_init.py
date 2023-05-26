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


async def test_flow_trello_adapter_get_board_lists(hass: HomeAssistant) -> None:
    """Test trello adapter retrieving the users lists on specified boards."""
    mock_client = _get_mock_client()
    id_boards = {
        "a_board_id": {"id": "a_board_id", "name": "A Board"},
        "a_board_id_2": {"id": "a_board_id_2", "name": "A Board 2"},
        "a_board_id_3": {"id": "a_board_id_3", "name": "A Board 3"},
    }
    selected_board_ids = ["a_board_id", "a_board_id_2"]

    actual_boards = TrelloAdapter(mock_client).get_board_lists(
        id_boards, selected_board_ids
    )

    assert actual_boards == {
        BOARD_ID: BOARD_LISTS,
        "a_board_id_2": {
            "id": "a_board_id_2",
            "name": "A Board 2",
            "lists": [
                {"id": "a_list_id_2", "name": "A List 2"},
                {"id": "a_list_id_3", "name": "A List 3"},
            ],
        },
    }


async def test_flow_trello_adapter_get_board_lists_none_selected(
    hass: HomeAssistant,
) -> None:
    """Test trello adapter retrieving the users lists with no selected boards."""
    mock_client = _get_mock_client()
    id_boards = {
        "a_board_id": {"id": "a_board_id", "name": "A Board"},
        "a_board_id_2": {"id": "a_board_id_2", "name": "A Board 2"},
        "a_board_id_3": {"id": "a_board_id_3", "name": "A Board 3"},
    }
    selected_board_ids = []

    actual_boards = TrelloAdapter(mock_client).get_board_lists(
        id_boards, selected_board_ids
    )

    assert not actual_boards


async def test_flow_trello_adapter_get_board_lists_bad_response(
    hass: HomeAssistant,
) -> None:
    """Test trello adapter retrieving the users lists with an error response."""
    mock_client = Mock()
    mock_client.fetch_json.return_value = [
        {"200": [{"id": "a_list_id", "name": "A List"}]},
        {
            "name": "NotFoundError",
            "message": "The requested resource was not found.",
            "statusCode": 404,
        },
    ]
    id_boards = {
        "a_board_id": {"id": "a_board_id", "name": "A Board"},
        "a_board_id_2": {"id": "a_board_id_2", "name": "A Board 2"},
        "a_board_id_3": {"id": "a_board_id_3", "name": "A Board 3"},
    }
    selected_board_ids = ["a_board_id", "a_board_id_2"]

    actual_boards = TrelloAdapter(mock_client).get_board_lists(
        id_boards, selected_board_ids
    )

    assert actual_boards == {BOARD_ID: BOARD_LISTS}


def _get_mock_client():
    mock_client = Mock()
    mock_client.fetch_json.return_value = [
        {"200": [{"id": "a_list_id", "name": "A List"}]},
        {
            "200": [
                {"id": "a_list_id_2", "name": "A List 2"},
                {"id": "a_list_id_3", "name": "A List 3"},
            ]
        },
    ]
    return mock_client
