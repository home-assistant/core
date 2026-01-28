"""Fixtures for saj tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pysaj
import pytest

from homeassistant.components.saj.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_SERIAL_NUMBER, MOCK_USER_INPUT_ETHERNET, MOCK_USER_INPUT_WIFI

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry_ethernet(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry for ethernet."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SAJ Solar Inverter",
        unique_id=MOCK_SERIAL_NUMBER,
        data=MOCK_USER_INPUT_ETHERNET,
        entry_id="saj_entry_ethernet",
    )


@pytest.fixture
def mock_config_entry_wifi(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry for wifi."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SAJ Solar Inverter",
        unique_id=MOCK_SERIAL_NUMBER,
        data=MOCK_USER_INPUT_WIFI,
        entry_id="saj_entry_wifi",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.saj.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pysaj() -> Generator[MagicMock]:
    """Mock the pysaj library."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(return_value=True)

        saj_cls.return_value = saj_instance

        # Mock Sensors class
        with patch("pysaj.Sensors") as sensors_cls:
            sensors_instance = MagicMock()
            sensors_cls.return_value = sensors_instance

            yield saj_instance


@pytest.fixture
def mock_pysaj_ethernet() -> Generator[MagicMock]:
    """Mock the pysaj library for ethernet devices."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(return_value=True)

        saj_cls.return_value = saj_instance

        # Mock Sensors class for ethernet
        with patch("pysaj.Sensors") as sensors_cls:
            sensors_instance = MagicMock()
            sensors_cls.return_value = sensors_instance

            yield saj_instance


@pytest.fixture
def mock_pysaj_wifi() -> Generator[MagicMock]:
    """Mock the pysaj library for wifi devices."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(return_value=True)

        saj_cls.return_value = saj_instance

        # Mock Sensors class for wifi
        with patch("pysaj.Sensors") as sensors_cls:
            sensors_instance = MagicMock()
            sensors_cls.return_value = sensors_instance

            yield saj_instance


@pytest.fixture
def mock_pysaj_connection_error() -> Generator[MagicMock]:
    """Mock the pysaj library with connection error."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnexpectedResponseException("Connection failed")
        )

        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors") as sensors_cls:
            sensors_instance = MagicMock()
            sensors_cls.return_value = sensors_instance

            yield saj_instance


@pytest.fixture
def mock_pysaj_auth_error() -> Generator[MagicMock]:
    """Mock the pysaj library with authentication error."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnauthorizedException("Auth failed")
        )

        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors") as sensors_cls:
            sensors_instance = MagicMock()
            sensors_cls.return_value = sensors_instance

            yield saj_instance
