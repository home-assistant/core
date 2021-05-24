"""Test the Kostal Plenticore helper module."""
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

from kostal.plenticore import ProcessDataCollection

from homeassistant.components.kostal_plenticore.helper import (
    ProcessDataUpdateCoordinator,
)


async def test_process_data_coordinator(hass):
    """Tests if the update coordinator only fetch started data."""

    logger = Mock()

    plenticore = AsyncMock()
    plenticore.client.get_process_data_values.return_value = {
        "m1": ProcessDataCollection([{"id": "d1", "value": "1"}]),
        "m2": ProcessDataCollection([{"id": "d2", "value": "2"}]),
    }

    coordinator = ProcessDataUpdateCoordinator(
        hass, logger, "test", timedelta(seconds=1), plenticore
    )
    coordinator.start_fetch_data("m1", "d1")
    coordinator.start_fetch_data("m1", "d2")
    coordinator.start_fetch_data("m2", "d1")
    coordinator.start_fetch_data("m2", "d2")
    coordinator.start_fetch_data("m2", "d2")  # double start
    coordinator.start_fetch_data("m3", "d1")
    coordinator.stop_fetch_data("m1", "d2")
    coordinator.stop_fetch_data("m2", "d1")
    coordinator.stop_fetch_data("m3", "d1")

    result = await coordinator._async_update_data()

    assert result == {
        "m1": {"d1": "1"},
        "m2": {"d2": "2"},
    }
    plenticore.client.get_process_data_values.assert_called_once_with(
        {"m1": ["d1"], "m2": ["d2"]}
    )
