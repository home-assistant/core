"""Tests for the TotalConnect init process."""

import logging
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from total_connect_client.exceptions import (
    AuthenticationError,
    ServiceUnavailable,
    TotalConnectError,
)

from homeassistant.components.totalconnect.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_reauth_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that reauth is started when we have login errors."""
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient",
    ) as mock_client:
        mock_client.side_effect = AuthenticationError()
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("mock_client")
@pytest.mark.parametrize(
    ("exception", "level"),
    [
        pytest.param(ServiceUnavailable, logging.INFO, id="unreachable"),
        pytest.param(TotalConnectError, logging.ERROR, id="error"),
    ],
)
async def test_update_failure_log_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_location: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    exception: type[Exception],
    level: int,
) -> None:
    """Test an unreachable service is logged at info level."""
    await setup_integration(hass, mock_config_entry)

    mock_location.get_panel_meta_data.side_effect = exception
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert [
        record.levelno
        for record in caplog.records
        if record.name == "homeassistant.components.totalconnect.coordinator"
        and record.levelno > logging.DEBUG
    ] == [level]
