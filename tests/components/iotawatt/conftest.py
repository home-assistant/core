"""Test fixtures for IoTaWatt."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.iotawatt import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def entry(hass):
    """Mock config entry added to HA."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_iotawatt(entry):
    """Mock iotawatt."""
    with patch("homeassistant.components.iotawatt.coordinator.Iotawatt") as mock:
        instance = mock.return_value
        instance.connect = AsyncMock(return_value=True)
        instance.update = AsyncMock()
        instance.getSensors.return_value = {"sensors": {}}
        yield instance
