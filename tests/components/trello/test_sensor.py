"""Test the trello config flow."""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from homeassistant.components.trello.const import Board, List
from homeassistant.components.trello.sensor import TrelloSensor, async_setup_entry
from homeassistant.core import HomeAssistant


async def test_sensor_setup_entry(hass: HomeAssistant) -> None:
    """Test sensors are set up as expected."""
    mock_config_entry = Mock(
        options={"boards": {"": ""}}, data={"api_key": "", "api_token": ""}
    )
    mock_add_entities = Mock()

    list1 = List("a_list_id", "A list", 0)
    list2 = List("a_list_id_2", "A list 2", 1)
    list3 = List("a_list_id_3", "A list 3", 2)
    board = Board("a_board_id", "A board", {"a_list_id": list1})
    board2 = Board(
        "a_board_id_2", "A board 2", {"a_list_id_2": list2, "a_list_id_3": list3}
    )
    mock_coordinator = AsyncMock()
    mock_coordinator.async_config_entry_first_refresh.return_value = MagicMock(
        return_value=3
    )
    mock_coordinator.data = {"a_board_id": board, "a_board_id_2": board2}

    with patch("homeassistant.components.trello.sensor.TrelloClient"), patch(
        "homeassistant.components.trello.sensor.TrelloDataUpdateCoordinator",
        return_value=mock_coordinator,
    ):
        await async_setup_entry(hass, mock_config_entry, mock_add_entities)

        expected_trello_sensors = [
            TrelloSensor(board, list1, mock_coordinator),
            TrelloSensor(board2, list2, mock_coordinator),
            TrelloSensor(board2, list3, mock_coordinator),
        ]

        for actual, expected in zip(
            mock_add_entities.call_args[0][0], expected_trello_sensors
        ):
            assert actual.native_value == expected.native_value
            assert actual.board == expected.board
            assert actual.list_id == expected.list_id
            assert actual.coordinator == expected.coordinator


async def test_empty_sensor_setup_entry(hass: HomeAssistant) -> None:
    """Test integration sets up even with no sensors."""
    mock_config_entry = Mock(
        options={"boards": {}}, data={"api_key": "", "api_token": ""}
    )
    mock_add_entities = Mock(options={"boards": []})

    with patch("homeassistant.components.trello.sensor.TrelloClient"), patch(
        "homeassistant.components.trello.sensor.TrelloDataUpdateCoordinator",
        autospec=True,
    ):
        await async_setup_entry(hass, mock_config_entry, mock_add_entities)

        mock_add_entities.assert_not_called()
