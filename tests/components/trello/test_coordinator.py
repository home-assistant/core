"""Test the trello config flow."""
from unittest.mock import Mock

from homeassistant.components.trello.const import Board, List
from homeassistant.components.trello.coordinator import TrelloDataUpdateCoordinator
from homeassistant.core import HomeAssistant


async def test_coordinator(hass: HomeAssistant) -> None:
    """Test coordinator determining card counts for lists."""
    board_ids = ["a_board_id", "a_board_id_2"]
    mock_client = Mock()
    mock_client.fetch_json.return_value = [
        {"200": {"id": "a_board_id", "name": "A board"}},
        {
            "200": [
                {
                    "id": "a_list_id",
                    "name": "A list",
                    "cards": [{"id": "a_card_id"}, {"id": "a_card_id_2"}],
                },
                {"id": "a_list_id_2", "name": "A list 2", "cards": []},
            ]
        },
    ]
    expected_boards = {
        "a_board_id": Board(
            "a_board_id",
            "A board",
            {
                "a_list_id": List("a_list_id", "A list", 2),
                "a_list_id_2": List("a_list_id_2", "A list 2", 0),
            },
        )
    }
    expected_paths = (
        "/boards/a_board_id?fields=name,/boards/a_board_id/lists?fields=name&cards=open&card_fields=idCard,"
        "/boards/a_board_id_2?fields=name,/boards/a_board_id_2/lists?fields=name&cards=open&card_fields=idCard"
    )

    coordinator = TrelloDataUpdateCoordinator(hass, mock_client, board_ids)
    actual_boards = coordinator._update()

    mock_client.fetch_json.assert_called_once_with(
        "batch", query_params={"urls": expected_paths}
    )
    assert actual_boards == expected_boards


async def test_coordinator_bad_response(hass: HomeAssistant) -> None:
    """Test coordinator determining card counts for lists."""
    board_ids = ["a_board_id", "a_board_id_2"]
    mock_client = Mock()
    mock_client.fetch_json.return_value = [
        {
            "name": "NotFoundError",
            "message": "The requested resource was not found.",
            "statusCode": 404,
        },
        {
            "200": [
                {"id": "a_list_id", "name": "A list", "cards": [{"id": "a_card_id"}]}
            ],
        },
    ]
    expected_boards = {"a_board_id": Board("a_board_id", "", {})}
    expected_paths = (
        "/boards/a_board_id?fields=name,/boards/a_board_id/lists?fields=name&cards=open&card_fields=idCard,"
        "/boards/a_board_id_2?fields=name,/boards/a_board_id_2/lists?fields=name&cards=open&card_fields=idCard"
    )

    coordinator = TrelloDataUpdateCoordinator(hass, mock_client, board_ids)
    actual_boards = coordinator._update()

    mock_client.fetch_json.assert_called_once_with(
        "batch", query_params={"urls": expected_paths}
    )
    assert actual_boards == expected_boards
