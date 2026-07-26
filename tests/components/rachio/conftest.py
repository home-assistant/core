"""Fixtures for the Rachio integration tests."""

from collections.abc import Generator
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.rachio.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

BASE_STATION_ID = "base123"
BASE_STATION_SERIAL = "SN123456"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test-api-key",
            CONF_WEBHOOK_ID: "rachio-test-webhook-id",
        },
        unique_id="test-user-id",
    )


@pytest.fixture
def mock_rachio() -> Generator[MagicMock]:
    """Return a mocked Rachio client."""
    with patch(
        "homeassistant.components.rachio.Rachio",
    ) as mock_rachio_cls:
        rachio = mock_rachio_cls.return_value

        rachio.person.info.return_value = (
            {"status": 200},
            {"id": "test-user-id"},
        )
        rachio.person.get.return_value = (
            {"status": 200},
            {
                "username": "testuser",
                "id": "test-user-id",
                "devices": [],
            },
        )
        rachio.valve.list_base_stations.return_value = (
            {"status": 200},
            {
                "baseStations": [
                    {
                        "id": BASE_STATION_ID,
                        "serialNumber": BASE_STATION_SERIAL,
                    }
                ]
            },
        )
        rachio.valve.list_valves.return_value = (
            {"status": 200},
            {"valves": []},
        )
        rachio.summary.get_valve_day_views.return_value = (
            {"status": 200},
            {"valveDayViews": []},
        )

        yield rachio


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
    request: pytest.FixtureRequest,
) -> MockConfigEntry:
    """Set up the Rachio integration for testing."""
    mock_config_entry.add_to_hass(hass)

    context = nullcontext()
    if platform := getattr(request, "param", None):
        context = patch("homeassistant.components.rachio.PLATFORMS", [platform])

    with (
        context,
        patch(
            "homeassistant.components.rachio.async_get_or_create_registered_webhook_id_and_url",
            return_value="http://example.com/webhook",
        ),
        patch("homeassistant.components.rachio.async_register_webhook"),
        patch("homeassistant.components.rachio.async_unregister_webhook"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
