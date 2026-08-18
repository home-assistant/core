"""Test configuration and fixtures for Imou integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyimouapi.ha_device import ImouHaDevice
import pytest

from homeassistant.components.imou.const import CONF_APP_ID, DOMAIN, PLATFORMS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONFIG_ENTRY_DATA, default_mock_devices

from tests.common import MockConfigEntry

PATCH_IMOU_OPENAPI_CLIENT = "homeassistant.components.imou.ImouOpenApiClient"
PATCH_CONFIG_FLOW_IMOU_OPENAPI_CLIENT = (
    "homeassistant.components.imou.config_flow.ImouOpenApiClient"
)
PATCH_IMOU_HA_DEVICE_MANAGER = "homeassistant.components.imou.ImouHaDeviceManager"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Imou",
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA,
        unique_id=CONFIG_ENTRY_DATA[CONF_APP_ID],
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_imou_openapi_client() -> Generator[AsyncMock]:
    """Mock ImouOpenApiClient for config flow and setup entry."""
    with (
        patch(
            PATCH_IMOU_OPENAPI_CLIENT,
            autospec=True,
        ) as mock_client,
        patch(
            PATCH_CONFIG_FLOW_IMOU_OPENAPI_CLIENT,
            new=mock_client,
        ),
    ):
        yield mock_client.return_value


@pytest.fixture
def imou_mock_devices(request: pytest.FixtureRequest) -> list[ImouHaDevice]:
    """Devices returned by ImouHaDeviceManager.async_get_devices (override via indirect)."""
    factory = getattr(request, "param", default_mock_devices)
    if callable(factory):
        return factory()
    return factory


@pytest.fixture
def mock_imou_ha_device_manager(
    imou_mock_devices: list[ImouHaDevice],
) -> Generator[MagicMock]:
    """Mock ImouHaDeviceManager with a default device list."""
    with patch(PATCH_IMOU_HA_DEVICE_MANAGER, autospec=True) as mock_manager:
        device_manager = mock_manager.return_value
        device_manager.async_get_devices.return_value = imou_mock_devices
        yield device_manager


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry so config flow tests do not load the full integration."""
    with patch(
        "homeassistant.components.imou.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def platforms(request: pytest.FixtureRequest) -> list[Platform]:
    """Return the platforms to set up (default: the integration's full list)."""
    return getattr(request, "param", PLATFORMS)


@pytest.fixture
def mock_camera_access_token() -> Generator[None]:
    """Stabilize camera access tokens for snapshot tests."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_openapi_client: AsyncMock,
    mock_imou_ha_device_manager: MagicMock,
    platforms: list[Platform],
) -> MagicMock:
    """Set up Imou with mocked library clients; returns the HA device manager mock."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.imou.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_imou_ha_device_manager
