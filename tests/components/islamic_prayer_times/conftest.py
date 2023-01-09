"""Conftest for islamic_prayer_times integration."""
import pytest
import requests_mock
from homeassistant.core import HomeAssistant

from tests.common import load_fixture
from . import REQUEST_URL


@pytest.fixture(autouse=True)
def set_utc(hass: HomeAssistant) -> None:
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


@pytest.fixture(autouse=True)
def requests_mock_fixture(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Fixture to provide a aioclient mocker."""
    requests_mock.get(
        REQUEST_URL,
        text=load_fixture("prayer_times.json", "islamic_prayer_times"),
    )
