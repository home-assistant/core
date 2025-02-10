"""Fixtures for WLED integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from wled import Device as WLEDDevice, Releases

from homeassistant.components.wled.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.123"},
        unique_id="aabbccddeeff",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.wled.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_onboarding() -> Generator[MagicMock]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def device_fixture() -> str:
    """Return the device fixture for a specific device."""
    return "rgb"


@pytest.fixture
def mock_wled_releases() -> Generator[MagicMock]:
    """Return a mocked WLEDReleases client."""
    with patch(
        "homeassistant.components.wled.coordinator.WLEDReleases", autospec=True
    ) as wled_releases_mock:
        wled_releases = wled_releases_mock.return_value
        wled_releases.releases.return_value = Releases(
            beta="1.0.0b5",
            stable="0.99.0",
        )

        yield wled_releases


@pytest.fixture
def mock_wled(
    device_fixture: str, mock_wled_releases: MagicMock
) -> Generator[MagicMock]:
    """Return a mocked WLED client."""
    with (
        patch(
            "homeassistant.components.wled.coordinator.WLED", autospec=True
        ) as wled_mock,
        patch("homeassistant.components.wled.config_flow.WLED", new=wled_mock),
    ):
        wled = wled_mock.return_value
        wled.update.return_value = WLEDDevice.from_dict(
            load_json_object_fixture(f"{device_fixture}.json", DOMAIN)
        )
        wled.connected = False
        wled.host = "127.0.0.1"

        yield wled


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> MockConfigEntry:
    """Set up the WLED integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Let some time pass so coordinators can be reliably triggered by bumping
    # time by SCAN_INTERVAL
    freezer.tick(1)

    return mock_config_entry
