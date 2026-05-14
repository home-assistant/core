"""Configuration for Huum tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from huum.const import SaunaStatus
from huum.schemas import HuumStatusResponse, SaunaConfig
import pytest

from homeassistant.components.huum.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_huum_client() -> Generator[AsyncMock]:
    """Mock the Huum API client."""
    with (
        patch(
            "homeassistant.components.huum.coordinator.Huum",
            autospec=True,
        ) as mock_cls,
        patch(
            "homeassistant.components.huum.config_flow.Huum",
            new=mock_cls,
        ),
    ):
        client = mock_cls.return_value
        client.status.return_value = HuumStatusResponse(
            status=SaunaStatus.ONLINE_NOT_HEATING,
            door_closed=True,
            temperature=30,
            sauna_name="123456",
            target_temperature=80,
            config=3,
            light=1,
            humidity=0,
            target_humidity=5,
            sauna_config=SaunaConfig(
                child_lock="OFF",
                max_heating_time=3,
                min_heating_time=0,
                max_temp=110,
                min_temp=40,
                max_timer=0,
                min_timer=0,
            ),
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.huum.async_setup_entry", return_value=True
    ) as setup_entry_mock:
        yield setup_entry_mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "huum@sauna.org",
            CONF_PASSWORD: "ukuuku",
        },
        entry_id="AABBCC112233",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [
        Platform.BINARY_SENSOR,
        Platform.CLIMATE,
        Platform.LIGHT,
        Platform.NUMBER,
        Platform.SENSOR,
    ]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_huum_client: AsyncMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Huum integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.huum.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
