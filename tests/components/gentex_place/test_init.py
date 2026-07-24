"""Test that the integration is initialized correctly."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from place.config import OAUTH2_TOKEN_URL
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_provider.enable.assert_awaited_once()
    mock_provider.discover.assert_awaited_once()
    mock_get_iot_credentials.assert_called_once_with(
        "mock-id-token", "mock-access-token"
    )
    mock_mqtt_client.connect.assert_called_once()


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_setup_seeds_shadow_from_discover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that initial shadow state is seeded from device discovery."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert "thing-001" in coordinator.data
    shadow = coordinator.data["thing-001"]
    assert shadow.co_alarm_status.value == 0
    assert shadow.heat_alarm_status.value == 0
    assert shadow.smoke_alarm_status.value == 0


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test the entry can be loaded and unloaded."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_mqtt_client.disconnect.assert_called_once()


@pytest.mark.usefixtures(
    "mock_provider",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a token refresh failure raises ConfigEntryAuthFailed."""
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        status=HTTPStatus.UNAUTHORIZED,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
