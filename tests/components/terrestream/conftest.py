"""Fixtures for local Terrestream sensors."""

from collections.abc import Generator
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from terrestream_local import Credentials

from homeassistant.core import HomeAssistant

UUID = "00000000-0000-4000-8000-000000000001"
HOST = "192.0.2.10"
CREDENTIALS = Credentials(UUID, "ab" * 32, "cd" * 32)


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add an entry containing synthetic pairing data."""
    entry = MockConfigEntry(
        domain="terrestream",
        unique_id=UUID,
        title="Terrestream",
        data={
            "host": HOST,
            "credentials": asdict(CREDENTIALS),
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_pair_device() -> Generator[AsyncMock]:
    """Mock the library's pairing entry point."""
    with patch(
        "homeassistant.components.terrestream.config_flow.pair_device",
        autospec=True,
    ) as mock_pair:
        yield mock_pair


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip integration setup when testing the config flow."""
    with patch(
        "homeassistant.components.terrestream.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_client(mock_pair_device: AsyncMock) -> Generator[MagicMock]:
    """Mock the published client at the HA boundary."""
    with patch("homeassistant.components.terrestream.Client", autospec=True) as factory:
        client = factory.return_value
        client.credentials = CREDENTIALS
        client.identity = AsyncMock(return_value={"paired": True})
        client.confirm = AsyncMock()
        client.command = AsyncMock(return_value={"ok": True})
        values = {
            "co2": 500,
            "pm1": 1,
            "pm25": 2,
            "pm4": 3,
            "pm10": 4,
            "temperature": 22,
            "humidity": 45,
            "pressure": 1013,
            "illuminance": 100,
            "computed_epa_aqi": 10,
            "voc_index": 123,
            "nox_index": 7,
        }
        client.refresh = AsyncMock(
            return_value={
                "model": "R500",
                "firmware": "4.1.0",
                "hardware": "test",
                "measurements": {
                    key: {"value": value, "available": True, "status": "valid"}
                    for key, value in values.items()
                },
            }
        )
        client.measurement_available.side_effect = lambda key: (
            client.refresh.return_value["measurements"][key]["available"]
        )
        mock_pair_device.return_value = (CREDENTIALS, client)
        yield client
