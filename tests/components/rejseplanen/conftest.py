"""Copyright 2024 Home Assistant Community Contributors.

Test configuration for Rejseplanen component.
"""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from py_rejseplan.api.departures import DeparturesAPIClient
from py_rejseplan.dataclasses.departure import DepartureType
from py_rejseplan.enums import TransportClass
import pytest

from homeassistant.components.rejseplanen.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def make_mock_departures():
    """Create mock departures."""
    mock_departure = MagicMock(spec=DepartureType)

    mock_departure.name = "Test Line"
    mock_departure.type = TransportClass.BUS
    mock_departure.cls_id = 1
    mock_departure.direction = "End Point St."
    mock_departure.stop = "Test Stop"
    mock_departure.time = (
        (datetime.now() + timedelta(minutes=5)).time().replace(second=0, microsecond=0)
    )
    mock_departure.date = datetime.now().date()
    mock_departure.track = "1A"
    mock_departure.final_stop = "End Station"
    mock_departure.messages = ["On time"]
    mock_departure.rtTime = (
        (datetime.now() + timedelta(minutes=7)).time().replace(second=0, microsecond=0)
    )
    mock_departure.rtDate = datetime.now().date()
    mock_departure.stopExtId = 123456
    return [mock_departure]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rejseplanen.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryDataWithId]:
    """Fixture for config subentries."""
    return [
        ConfigSubentryDataWithId(
            data={
                CONF_STOP_ID: "stop-123",
                CONF_NAME: "Work",
            },
            subentry_type="stop",
            title="Work",
            subentry_id="work-subentry-id",
            unique_id=None,
        ),
        ConfigSubentryDataWithId(
            data={
                CONF_STOP_ID: "stop-456",
                CONF_NAME: "Gym",
            },
            subentry_type="stop",
            title="Gym",
            subentry_id="gym-subentry-id",
            unique_id=None,
        ),
        ConfigSubentryDataWithId(
            data={
                CONF_STOP_ID: "home-stop-789",
                CONF_NAME: "Home Location",
            },
            subentry_type="location",
            title="Home",
            subentry_id="home-subentry-id",
            unique_id=None,
        ),
    ]


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_subentries: list[ConfigSubentryDataWithId]
) -> MockConfigEntry:
    """Fixture for a config entry with subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        entry_id="123456789",
        subentries_data=[*mock_subentries],
    )


@pytest.fixture(name="mock_api")
def mock_rejseplanen_coordinator(hass: HomeAssistant) -> Generator[Mock]:
    """Mock Rejseplanen setup."""

    with (
        patch(
            "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient",
            spec=DeparturesAPIClient,
        ) as mock_api_class,
    ):
        mock_api = mock_api_class.return_value
        mock_api.get_departures.return_value = make_mock_departures()

    return mock_api


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: Mock,
) -> AsyncGenerator[Any, Any]:
    """Fixture to set up the integration."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield
