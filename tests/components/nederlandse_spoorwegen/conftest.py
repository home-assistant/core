"""Fixtures for Nederlandse Spoorwegen tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.nederlandse_spoorwegen import DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api_wrapper():
    """Mock NS API wrapper."""
    wrapper = MagicMock()
    wrapper.validate_api_key = AsyncMock(return_value=True)
    wrapper.get_stations = AsyncMock(return_value=[])
    wrapper.get_trips = AsyncMock(return_value=[])
    wrapper.get_station_codes = MagicMock(return_value=set())
    return wrapper


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
        options={},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )


@pytest.fixture
def mock_coordinator():
    """Mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data = {"routes": {}}
    return coordinator


@pytest.fixture
def mock_hass():
    """Mock hass."""
    return MagicMock()
