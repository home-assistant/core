"""Common fixtures for the Roth Touchline SL tests."""

from collections.abc import Generator
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.touchline_sl.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


class FakeModule(NamedTuple):
    """Fake Module used for unit testing only."""

    name: str
    id: str


def make_mock_zone(
    zone_id: int = 1, name: str = "Zone 1", alarm: str | None = None
) -> MagicMock:
    """Return a mock Zone with configurable alarm state."""
    zone = MagicMock()
    zone.id = zone_id
    zone.name = name
    zone.temperature = 21.5
    zone.target_temperature = 22.0
    zone.humidity = 45
    zone.mode = "constantTemp"
    zone.algorithm = "heating"
    zone.relay_on = False
    zone.alarm = alarm
    zone.schedule = None
    zone.enabled = True
    zone.signal_strength = 100
    zone.battery_level = None
    return zone


def make_mock_module(zones: list) -> MagicMock:
    """Return a mock module with the given zones."""
    module = MagicMock()
    module.id = "deadbeef"
    module.name = "Foobar"
    module.type = "SL"
    module.version = "1.0"
    module.zones = AsyncMock(return_value=zones)
    module.schedules = AsyncMock(return_value=[])
    return module


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.touchline_sl.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_touchlinesl_client() -> Generator[AsyncMock]:
    """Mock a pytouchlinesl client."""
    with (
        patch(
            "homeassistant.components.touchline_sl.TouchlineSL",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.touchline_sl.config_flow.TouchlineSL",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.user_id.return_value = 12345
        client.modules.return_value = [FakeModule(name="Foobar", id="deadbeef")]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="TouchlineSL",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        unique_id="12345",
    )
