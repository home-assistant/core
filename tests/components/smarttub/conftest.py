"""Common fixtures for smarttub tests."""

import pytest
import smarttub

from homeassistant.components.smarttub.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.async_mock import create_autospec
from tests.common import MockConfigEntry


@pytest.fixture
def config_data():
    """Provide configuration data for tests."""
    return {CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"}


@pytest.fixture
def config_entry(config_data):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        options={},
    )


@pytest.fixture(name="spa")
def mock_spa():
    """Mock a SmartTub.Spa."""

    mock_spa = create_autospec(smarttub.Spa, instance=True)
    mock_spa.id = "mockspa1"
    mock_spa.brand = "mockbrand1"
    mock_spa.model = "mockmodel1"
    mock_spa.get_status.return_value = {
        "setTemperature": "settemp1",
        "water": {"temperature": "watertemp1"},
        "heater": "heaterstatus1",
    }
    return mock_spa


@pytest.fixture(name="coordinator")
def mock_coordinator():
    """Mock DataUpdateCoordinator."""

    mock_coordinator = create_autospec(DataUpdateCoordinator, instance=True)
    mock_coordinator.last_update_success = True
    mock_coordinator.data = {}

    return mock_coordinator
