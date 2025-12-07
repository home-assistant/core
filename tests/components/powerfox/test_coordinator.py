"""Tests for the Powerfox coordinators."""

from __future__ import annotations

from unittest.mock import AsyncMock

from powerfox import (
    DeviceType,
    PowerfoxAuthenticationError,
    PowerfoxConnectionError,
    PowerfoxNoDataError,
)
import pytest

from homeassistant.components.powerfox.coordinator import (
    PowerfoxReportDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import create_empty_config_entry, create_mock_device


@pytest.mark.parametrize(
    "error",
    [
        PowerfoxConnectionError("boom"),
        PowerfoxNoDataError("boom"),
    ],
)
async def test_report_coordinator_update_failed(
    hass: HomeAssistant, error: Exception
) -> None:
    """Ensure connection/no data errors are wrapped for report calls."""
    client = AsyncMock()
    client.report.side_effect = error
    coordinator = PowerfoxReportDataUpdateCoordinator(
        hass,
        create_empty_config_entry(),
        client,
        create_mock_device(DeviceType.GAS_METER),
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_report_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Ensure auth errors trigger reauth for report calls."""
    client = AsyncMock()
    client.report.side_effect = PowerfoxAuthenticationError("bad creds")
    coordinator = PowerfoxReportDataUpdateCoordinator(
        hass,
        create_empty_config_entry(),
        client,
        create_mock_device(DeviceType.GAS_METER),
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
