"""Test configuration and fixtures for Imou integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyimouapi.ha_device import ImouHaDevice
import pytest

from homeassistant.components.imou.const import CONF_APP_ID, DOMAIN
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
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_openapi_client: AsyncMock,
    mock_imou_ha_device_manager: MagicMock,
) -> MagicMock:
    """Set up Imou with mocked library clients; returns the HA device manager mock."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_imou_ha_device_manager


async def _init_integration_with_platforms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Set up Imou loading only the requested platforms."""
    with patch("homeassistant.components.imou.PLATFORMS", platforms):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.fixture
async def init_button_platform_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_openapi_client: AsyncMock,
    mock_imou_ha_device_manager: MagicMock,
) -> MagicMock:
    """Set up Imou with only the button platform loaded."""
    await _init_integration_with_platforms(hass, mock_config_entry, [Platform.BUTTON])
    return mock_imou_ha_device_manager


@pytest.fixture
async def init_switch_platform_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_openapi_client: AsyncMock,
    mock_imou_ha_device_manager: MagicMock,
) -> MagicMock:
    """Set up Imou with only the switch platform loaded."""
    await _init_integration_with_platforms(hass, mock_config_entry, [Platform.SWITCH])
    return mock_imou_ha_device_manager


@pytest.fixture
async def init_camera_platform_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_openapi_client: AsyncMock,
    mock_imou_ha_device_manager: MagicMock,
) -> MagicMock:
    """Set up Imou with only the camera platform loaded."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await _init_integration_with_platforms(
            hass, mock_config_entry, [Platform.CAMERA]
        )
    return mock_imou_ha_device_manager


@pytest.fixture
async def init_sensor_platform_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_openapi_client: AsyncMock,
    mock_imou_ha_device_manager: MagicMock,
) -> MagicMock:
    """Set up Imou with only the sensor platform loaded."""
    await _init_integration_with_platforms(hass, mock_config_entry, [Platform.SENSOR])
    return mock_imou_ha_device_manager


@pytest.fixture
async def init_integration_stable_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_openapi_client: AsyncMock,
    mock_imou_ha_device_manager: MagicMock,
) -> MagicMock:
    """Set up Imou with stable camera access tokens for snapshot tests."""
    mock_config_entry.add_to_hass(hass)
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_imou_ha_device_manager
