"""Test fixtures for Autoskope integration."""

from collections.abc import Generator
from json import loads
from unittest.mock import AsyncMock, patch

from autoskope_client.models import Vehicle
import pytest

from homeassistant.components.autoskope.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Autoskope (test_user)",
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_HOST: DEFAULT_HOST,
        },
        unique_id=f"test_user@{DEFAULT_HOST}",
        entry_id="01AUTOSKOPE_TEST_ENTRY",
    )


@pytest.fixture
def mock_vehicles() -> list[Vehicle]:
    """Return a list of mock vehicles from fixture data."""
    data = loads(load_fixture("vehicles.json", DOMAIN))
    return [
        Vehicle.from_api(vehicle, data["positions"]) for vehicle in data["vehicles"]
    ]


@pytest.fixture
def mock_autoskope_client(mock_vehicles: list[Vehicle]) -> Generator[AsyncMock]:
    """Mock the Autoskope API client."""
    with (
        patch(
            "homeassistant.components.autoskope.AutoskopeApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.autoskope.config_flow.AutoskopeApi",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.connect.return_value = None
        client.get_vehicles.return_value = mock_vehicles
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.autoskope.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
