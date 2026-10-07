"""Test fixtures for IoTaWatt."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.iotawatt.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def entry_options() -> dict[str, Any]:
    """Options of the mock config entry, overridden by tests."""
    return {}


@pytest.fixture
def entry(hass: HomeAssistant, entry_options: dict[str, Any]) -> MockConfigEntry:
    """Mock config entry added to HA."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Device",
        data={"host": "1.2.3.4"},
        options=entry_options,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_iotawatt(entry: MockConfigEntry) -> Generator[MagicMock]:
    """Mock iotawatt."""
    with patch("homeassistant.components.iotawatt.coordinator.Iotawatt") as mock:
        instance = mock.return_value
        instance.connect = AsyncMock(return_value=True)
        instance.update = AsyncMock()
        instance.getSensors.return_value = {"sensors": {}}
        yield instance
