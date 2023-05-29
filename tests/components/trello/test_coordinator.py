"""Test the trello config flow."""
from unittest.mock import Mock

from homeassistant.components.trello.coordinator import TrelloDataUpdateCoordinator
from homeassistant.core import HomeAssistant


async def test_coordinator(hass: HomeAssistant) -> None:
    """Test coordinator determining card counts for lists."""
    board_ids = ["a_board_id", "a_board_id_2"]
    mock_client = Mock()
    mock_client.fetch_json.return_value = [
        {
            "200": [
                {"id": "a_list_id", "name": "A list", "cards": [{"id": "a_card_id"}]}
            ],
        },
        {
            "200": [
                {
                    "id": "a_list_id_2",
                    "name": "A list 2",
                    "cards": [{"id": "a_card_id_2"}, {"id": "a_card_id_3"}],
                },
                {"id": "a_list_id_3", "name": "A list 3", "cards": []},
            ]
        },
    ]
    expected_card_counts = {"a_list_id": 1, "a_list_id_2": 2, "a_list_id_3": 0}
    expected_paths = (
        "/boards/a_board_id/lists?fields=name&cards=open&card_fields=none,"
        "/boards/a_board_id_2/lists?fields=name&cards=open&card_fields=none"
    )

    coordinator = TrelloDataUpdateCoordinator(hass, mock_client, board_ids)
    actual_card_counts = coordinator._update()

    mock_client.fetch_json.assert_called_once_with(
        "batch", query_params={"urls": expected_paths}
    )
    assert actual_card_counts == expected_card_counts


async def test_coordinator_bad_response(hass: HomeAssistant) -> None:
    """Test coordinator determining card counts for lists."""
    board_ids = ["a_board_id", "a_board_id_2"]
    mock_client = Mock()
    mock_client.fetch_json.return_value = [
        {
            "200": [
                {"id": "a_list_id", "name": "A list", "cards": [{"id": "a_card_id"}]}
            ],
        },
        {
            "name": "NotFoundError",
            "message": "The requested resource was not found.",
            "statusCode": 404,
        },
    ]
    expected_card_counts = {"a_list_id": 1}
    expected_paths = (
        "/boards/a_board_id/lists?fields=name&cards=open&card_fields=none,"
        "/boards/a_board_id_2/lists?fields=name&cards=open&card_fields=none"
    )

    coordinator = TrelloDataUpdateCoordinator(hass, mock_client, board_ids)
    actual_card_counts = coordinator._update()

    mock_client.fetch_json.assert_called_once_with(
        "batch", query_params={"urls": expected_paths}
    )
    assert actual_card_counts == expected_card_counts
