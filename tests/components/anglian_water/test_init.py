"""Test Anglian Water init."""

from unittest.mock import AsyncMock, MagicMock

from pyanglianwater.exceptions import (
    ConsentRequiredError,
    ExpiredAccessTokenError,
    SelfAssertedError,
    SmartMeterUnavailableError,
)
import pytest

from homeassistant.components.anglian_water.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CONSENT_REQUIRED_ISSUE_ID

from tests.common import MockConfigEntry


async def test_setup_unload_entry(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    mock_anglian_water_authenticator: MagicMock,
) -> None:
    """Test successful setup and unload of the config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception_type", "expected_state"),
    [
        pytest.param(
            ExpiredAccessTokenError,
            ConfigEntryState.SETUP_ERROR,
            id="expired_access_token",
        ),
        pytest.param(
            SelfAssertedError,
            ConfigEntryState.SETUP_ERROR,
            id="self_asserted",
        ),
    ],
)
async def test_setup_auth_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    mock_anglian_water_authenticator: MagicMock,
    exception_type: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test setup failure due to authentication errors."""
    mock_anglian_water_authenticator.send_refresh_request.side_effect = exception_type

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_setup_consent_required(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    mock_anglian_water_authenticator: MagicMock,
) -> None:
    """Test setup raises ConfigEntryNotReady and creates a repair issue when consent is required."""
    mock_anglian_water_authenticator.send_refresh_request.side_effect = (
        ConsentRequiredError
    )

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    # Assert issue was created
    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, CONSENT_REQUIRED_ISSUE_ID) is not None

    # Test that the issue is deleted once consent is granted
    mock_anglian_water_authenticator.send_refresh_request.side_effect = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, CONSENT_REQUIRED_ISSUE_ID) is None


async def test_setup_smart_meter_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    mock_anglian_water_authenticator: MagicMock,
) -> None:
    """Test setup fails when the smart meter is unavailable."""
    mock_anglian_water_client.validate_smart_meter.side_effect = (
        SmartMeterUnavailableError
    )

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
