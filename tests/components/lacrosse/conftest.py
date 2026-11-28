"""Fixtures for LaCrosse integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant

ENTRY_DATA = {
    "device": "/dev/ttyUSB0",
    "baud": 57600,
    "datarate": 57600,
    "frequency": 868300,
    "led": True,
    "toggle_interval": 5,
    "toggle_mask": 255,
}


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryDataWithId]:
    """Return configured sensor subentries."""
    return [
        ConfigSubentryDataWithId(
            data={"id": sensor_id, "name": name},
            subentry_type="sensor",
            title=name,
            unique_id=str(sensor_id),
            subentry_id=f"sensor_{sensor_id}",
        )
        for sensor_id, name in ((1, "Outdoor"), (2, "LaCrosse sensor 2"))
    ]


@pytest.fixture
def mock_unique_id() -> str | None:
    """Return the receiver unique ID."""
    return None


@pytest.fixture
def mock_config_entry(
    mock_subentries: list[ConfigSubentryDataWithId], mock_unique_id: str | None
) -> MockConfigEntry:
    """Return a receiver with configured sensor subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id=mock_unique_id,
        subentries_data=mock_subentries,
    )


@pytest.fixture
def config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Add the receiver to Home Assistant."""
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config entry setup during config flow tests."""
    with patch(
        "homeassistant.components.lacrosse.async_setup_entry", return_value=None
    ) as mock:
        yield mock


@pytest.fixture
def mock_lacrosse() -> Generator[None]:
    """Prevent config-flow tests from opening a serial receiver."""
    with patch("homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse"):
        yield
