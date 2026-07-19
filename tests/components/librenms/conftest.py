"""Common fixtures for the LibreNMS tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

from aiolibrenms.devices import LibrenmsDevices
from aiolibrenms.system import LibrenmsSystem
import pytest

from homeassistant.components.librenms.const import DOMAIN

from .const import MOCK_CONFIG_ENTRY_DATA, MOCK_DEVICES_DATA, MOCK_SYSTEM_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.librenms.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA,
        title="librenms",
    )


@pytest.fixture
def mock_librenms_system() -> AsyncMock:
    """Mock the LibreNMS system api."""
    mock = AsyncMock(spec=LibrenmsSystem)
    mock.async_get_system_info.return_value = MOCK_SYSTEM_DATA
    return mock


@pytest.fixture
def mock_librenms_devices() -> AsyncMock:
    """Mock the LibreNMS devices api."""
    mock = AsyncMock(spec=LibrenmsDevices)
    mock.async_get_devices.return_value = MOCK_DEVICES_DATA
    return mock


@pytest.fixture
async def mock_librenms(
    mock_librenms_devices: AsyncMock,
    mock_librenms_system: AsyncMock,
) -> AsyncGenerator[AsyncMock]:
    """Mock the LibreNMS API."""
    with (
        patch(
            "homeassistant.components.librenms.coordinator.Librenms", autospec=True
        ) as mock_librenms,
        patch(
            "homeassistant.components.librenms.config_flow.Librenms", new=mock_librenms
        ),
    ):
        client = mock_librenms.return_value
        client.devices = mock_librenms_devices
        client.system = mock_librenms_system
        yield client
