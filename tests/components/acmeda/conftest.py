"""Define fixtures available for all Acmeda tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_roller() -> MagicMock:
    """Return a mocked Acmeda roller."""
    roller = MagicMock()
    roller.id = 1234567890123
    roller.name = "Roller"
    roller.battery = 50
    roller.type = 1
    roller.closed_percent = 50
    return roller


@pytest.fixture
def mock_hub(mock_roller: MagicMock) -> Generator[MagicMock]:
    """Mock the aiopulse Hub client."""
    with patch("homeassistant.components.acmeda.hub.aiopulse.Hub") as hub_class:
        hub = hub_class.return_value
        hub.id = "hub-id"
        hub.host = "127.0.0.1"
        hub.rollers = {mock_roller.id: mock_roller}
        hub.run = AsyncMock()
        hub.stop = AsyncMock()
        yield hub


@pytest.fixture
def mock_hub_run() -> Generator[AsyncMock]:
    """Mock the hub run method."""
    with patch("homeassistant.components.acmeda.hub.aiopulse.Hub.run") as mock_run:
        yield mock_run
