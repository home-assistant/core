"""Test helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from tests.common import mock_device_registry, mock_registry


@pytest.fixture
def mock_solarlog():
    """Build a fixture for the SolarLog API that connects successfully and returns one device."""

    mock_solarlog_api = AsyncMock()
    with patch(
        "homeassistant.components.solarlog.config_flow.SolarLogConnector",
        return_value=mock_solarlog_api,
    ) as mock_solarlog_api:
        mock_solarlog_api.return_value.test_connection.return_value = True
        yield mock_solarlog_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.solarlog.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="test_connect")
def mock_test_connection():
    """Mock a successful _test_connection."""
    with patch(
        "homeassistant.components.solarlog.config_flow.SolarLogConfigFlow._test_connection",
        return_value=True,
    ):
        yield


@pytest.fixture(name="device_reg")
def device_reg_fixture(hass: HomeAssistant):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture(name="entity_reg")
def entity_reg_fixture(hass: HomeAssistant):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)
