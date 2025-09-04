"""Common fixtures for the Duke Energy tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.duke_energy.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.typing import RecorderInstanceContextManager


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.duke_energy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Mock a successful Duke Energy API."""
    with (
        patch(
            "homeassistant.components.duke_energy.config_flow.DukeEnergy",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.duke_energy.coordinator.DukeEnergy",
            new=mock_api,
        ),
    ):
        api = mock_api.return_value
        api.authenticate.return_value = {
            "loginEmailAddress": "TEST@EXAMPLE.COM",
            "internalUserID": "test-username",
        }
        api.get_meters.return_value = {}
        yield api


@pytest.fixture
def mock_api_with_meters(mock_api: AsyncMock) -> AsyncMock:
    """Mock a successful Duke Energy API with meters."""
    mock_api.get_meters.return_value = {
        "123": {
            "serialNum": "123",
            "serviceType": "ELECTRIC",
            "agreementActiveDate": "2000-01-01",
        },
    }
    mock_api.get_energy_usage.return_value = {
        "data": {
            dt_util.now(): {
                "energy": 1.3,
                "temperature": 70,
            }
        },
        "missing": [],
    }
    return mock_api
