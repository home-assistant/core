"""Fixtures for Lunatone tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from lunatone_rest_api_client import Device
import pytest

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.const import CONF_URL

from . import BASE_URL, DEVICES_DATA, INFO_DATA, SERIAL_NUMBER

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lunatone.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_lunatone_auth() -> Generator[AsyncMock]:
    """Mock a Lunatone auth object."""
    with (
        patch(
            "homeassistant.components.lunatone.Auth",
            autospec=True,
        ) as mock_auth,
        patch(
            "homeassistant.components.lunatone.config_flow.Auth",
            new=mock_auth,
        ),
    ):
        auth = mock_auth.return_value
        auth.base_url = BASE_URL
        yield auth


@pytest.fixture
def mock_lunatone_devices(mock_lunatone_auth: AsyncMock) -> Generator[AsyncMock]:
    """Mock a Lunatone devices object."""
    with patch(
        "homeassistant.components.lunatone.Devices",
        autospec=True,
    ) as mock_devices:
        devices = mock_devices.return_value
        devices._auth = mock_lunatone_auth
        devices._data = DEVICES_DATA
        devices.data = devices._data
        devices.devices = [
            Device(devices._auth, device_data) for device_data in devices.data.devices
        ]
        yield devices


@pytest.fixture
def mock_lunatone_info(mock_lunatone_auth: AsyncMock) -> Generator[AsyncMock]:
    """Mock a Lunatone info object."""
    with (
        patch(
            "homeassistant.components.lunatone.Info",
            autospec=True,
        ) as mock_info,
        patch(
            "homeassistant.components.lunatone.config_flow.Info",
            new=mock_info,
        ),
    ):
        info = mock_info.return_value
        info._auth = mock_lunatone_auth
        info.data = INFO_DATA
        info.name = info.data.name
        info.version = info.data.version
        info.serial_number = info.data.device.serial
        yield info


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=f"Lunatone {SERIAL_NUMBER}",
        domain=DOMAIN,
        data={CONF_URL: BASE_URL},
        unique_id=str(SERIAL_NUMBER),
    )
