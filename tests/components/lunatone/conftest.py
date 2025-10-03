"""Fixtures for Lunatone tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, PropertyMock, patch

from lunatone_rest_api_client import Device, Devices
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
def mock_lunatone_devices() -> Generator[AsyncMock]:
    """Mock a Lunatone devices object."""

    def build_devices_mock(devices: Devices):
        device_list = []
        for device_data in devices.data.devices:
            device = AsyncMock(spec=Device)
            device.data = device_data
            device.id = device.data.id
            device.name = device.data.name
            device.is_on = device.data.features.switchable.status
            device_list.append(device)
        return device_list

    with patch(
        "homeassistant.components.lunatone.Devices", autospec=True
    ) as mock_devices:
        devices = mock_devices.return_value
        devices.data = DEVICES_DATA
        type(devices).devices = PropertyMock(
            side_effect=lambda d=devices: build_devices_mock(d)
        )
        yield devices


@pytest.fixture
def mock_lunatone_info() -> Generator[AsyncMock]:
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
