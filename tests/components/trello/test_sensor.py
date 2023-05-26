"""Test the trello config flow."""
from unittest.mock import Mock, patch

from homeassistant.components.trello.sensor import async_setup_entry
from homeassistant.core import HomeAssistant

from . import BOARD_LISTS


async def test_sensor_setup_entry(hass: HomeAssistant) -> None:
    """Test sensors are set up as expected."""
    a_list = {"id": "a_list_id", "name": "A List"}
    a_list_2 = {"id": "a_list_id_2", "name": "A List 2"}
    a_list_3 = {"id": "a_list_id_3", "name": "A List 3"}
    a_board = BOARD_LISTS
    a_board_2 = {
        "id": "a_board_id_2",
        "name": "A Board 2",
        "lists": [a_list_2, a_list_3],
    }
    boards = {"a_board_id": a_board, "a_board_id_2": a_board_2}
    mock_config_entry = Mock(
        options={"boards": boards}, data={"api_key": "", "api_token": ""}
    )
    mock_add_entities = Mock(options={"boards": []})

    with patch("homeassistant.components.trello.sensor.TrelloClient"), patch(
        "homeassistant.components.trello.sensor.TrelloSensor"
    ) as mock_trello_sensor, patch(
        "homeassistant.components.trello.sensor.TrelloDataUpdateCoordinator",
        autospec=True,
    ):
        await async_setup_entry(hass, mock_config_entry, mock_add_entities)

        mock_trello_sensors = [
            mock_trello_sensor(a_board, a_list),
            mock_trello_sensor(a_board_2, a_list_2),
            mock_trello_sensor(a_board_2, a_list_3),
        ]
        mock_add_entities.assert_called_once_with(mock_trello_sensors, True)


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
