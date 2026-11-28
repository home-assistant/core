"""Fixtures for the Danfoss Air tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pydanfossair.commands import ReadCommand, UpdateCommand
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.danfoss_air.const import DOMAIN
from homeassistant.const import CONF_HOST

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
    """Mock the pydanfossair client in the integration and the config flow."""
    with (
        patch(
            "homeassistant.components.danfoss_air.DanfossClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.danfoss_air.config_flow.DanfossClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.command.side_effect = _command
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Danfoss Air config entry."""
    return MockConfigEntry(
        domain=DOMAIN, title="Danfoss Air", data={CONF_HOST: "192.0.2.1"}
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip setting up the config entry."""
    with patch(
        "homeassistant.components.danfoss_air.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup
