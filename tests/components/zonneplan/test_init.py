"""Test the Zonneplan integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pyzonneplan import (
    BatteryInstallation,
    Token,
    ZonneplanAuthenticationError,
    ZonneplanConnectionError,
    ZonneplanRateLimitError,
    ZonneplanRequestError,
    ZonneplanTimeoutError,
)

from homeassistant.components.zonneplan.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        pytest.param(
            ZonneplanAuthenticationError("bad token"),
            ConfigEntryState.SETUP_ERROR,
            id="authentication_error",
        ),
        pytest.param(
            ZonneplanTimeoutError("timed out"),
            ConfigEntryState.SETUP_RETRY,
            id="timeout_error",
        ),
        pytest.param(
            ZonneplanConnectionError("boom"),
            ConfigEntryState.SETUP_RETRY,
            id="connection_error",
        ),
        pytest.param(
            ZonneplanRateLimitError("slow down", retry_after=30),
            ConfigEntryState.SETUP_RETRY,
            id="rate_limit_error",
        ),
        pytest.param(
            ZonneplanRequestError("rejected"),
            ConfigEntryState.SETUP_RETRY,
            id="request_error",
        ),
    ],
)
async def test_setup_entry_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test errors while fetching data mark the entry for retry."""
    mock_zonneplan_client.async_get_account.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(ZonneplanConnectionError("boom"), id="connection_error"),
        pytest.param([BatteryInstallation()], id="battery_not_found"),
    ],
)
async def test_setup_entry_battery_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    side_effect: Exception | list[BatteryInstallation],
) -> None:
    """Test a failing home battery fetch marks the entry for retry."""
    mock_zonneplan_client.async_get_battery.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_rate_limit_postpones_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rate limit schedules the next update after its Retry-After."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_zonneplan_client.async_get_account.call_count == 1

    mock_zonneplan_client.async_get_account.side_effect = ZonneplanRateLimitError(
        "slow down", retry_after=120
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_zonneplan_client.async_get_account.call_count == 2

    # The next update follows Retry-After instead of the 15-minute interval.
    mock_zonneplan_client.async_get_account.side_effect = None
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_zonneplan_client.async_get_account.call_count == 3


async def test_setup_entry_persists_rotated_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test a rotated refresh token is persisted to the config entry."""
    rotated_token = Token(
        access_token="rotated-access-token",
        refresh_token="rotated-refresh-token",
        expires_at=dt_util.utcnow() + timedelta(hours=1),
    )
    mock_zonneplan_client.token = rotated_token
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_TOKEN] == rotated_token.as_dict()
