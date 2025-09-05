"""Fixtures for Lunatone tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from lunatone_rest_api_client.models import DeviceInfoData, InfoData
import pytest

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def base_url() -> str:
    """Base URL fixture."""
    return "http://10.0.0.131"


@pytest.fixture
def serial_number() -> int:
    """Serial number fixture."""
    return 12345


@pytest.fixture
def version() -> str:
    """Version fixture."""
    return "v1.14.1/1.4.3"


@pytest.fixture
def info_data(version: str, serial_number: int) -> InfoData:
    """Info data fixture."""
    return InfoData(
        name="Test",
        version=version,
        device=DeviceInfoData(
            serial=serial_number,
            gtin=192837465,
            pcb="2a",
            articleNumber=87654321,
            productionYear=20,
            productionWeek=1,
        ),
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lunatone.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_lunatone_auth(base_url: str) -> Generator[AsyncMock]:
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
        auth.base_url = base_url
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
        yield devices


@pytest.fixture
def mock_lunatone_info(
    info_data: InfoData, mock_lunatone_auth: AsyncMock, version: str, serial_number: int
) -> Generator[AsyncMock]:
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
        info.data = info_data
        info.name = info.data.name
        info.version = info.data.version
        info.serial_number = info.data.device.serial
        yield info


@pytest.fixture
def mock_config_entry(base_url: str) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Lunatone 12345",
        domain=DOMAIN,
        data={CONF_URL: base_url},
        unique_id="12345",
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Lunatone integration for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("asyncio.sleep"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
