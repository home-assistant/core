"""Fixtures for the Danfoss Air tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pydanfossair.commands import ReadCommand, UpdateCommand
import pytest

# Register values as reported by a Danfoss Air A2, keyed by ReadCommand name.
READ_VALUES: dict[str, float | bool] = {
    "exhaustTemperature": 15.65,
    "outdoorTemperature": 14.7,
    "supplyTemperature": 20.75,
    "extractTemperature": 21.78,
    "humidity": 57.25,
    "filterPercent": 10.59,
    "bypass": False,
    "fan_step": 54,
    "fan_speed_percent": 54,
    "supply_fan_speed": 1716,
    "exhaust_fan_speed": 2019,
    "away_mode": False,
    "boost": False,
    "battery_percent": 94,
    "automatic_bypass": True,
}


def _command(command: ReadCommand | UpdateCommand) -> float | bool:
    """Answer a read with its canned value and a write with its read-back state."""
    if isinstance(command, ReadCommand):
        return READ_VALUES[command.name]
    return not command.name.endswith("deactivate")


@pytest.fixture
def mock_danfoss_client() -> Generator[MagicMock]:
    """Mock the pydanfossair client."""
    with patch(
        "homeassistant.components.danfoss_air.DanfossClient", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.command.side_effect = _command
        yield client
