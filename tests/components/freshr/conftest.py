"""Common fixtures for the Fresh-r tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyfreshr.models import DeviceReadings, DeviceSummary
import pytest

from homeassistant.components.freshr.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_ID = "SN001"

MOCK_DEVICE_CURRENT = DeviceReadings(
    t1=21.5,
    t2=5.3,
    co2=850,
    hum=45,
    flow=0.12,
    dp=10.2,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.freshr.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-user", CONF_PASSWORD: "test-pass"},
        unique_id="test-user",
    )


@pytest.fixture
def mock_freshr_client() -> Generator[MagicMock]:
    """Return a mocked FreshrClient."""
    with (
        patch(
            "homeassistant.components.freshr.coordinator.FreshrClient", autospec=True
        ) as mock_client_class,
        patch(
            "homeassistant.components.freshr.config_flow.FreshrClient",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.logged_in = False
        client.fetch_devices.return_value = [DeviceSummary(id=DEVICE_ID)]
        client.fetch_device_current.return_value = MOCK_DEVICE_CURRENT
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Fresh-r integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
