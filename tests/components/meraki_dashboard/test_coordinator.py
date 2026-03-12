"""Test Meraki Dashboard coordinator behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.meraki_dashboard.api import (
    MerakiDashboardApiRateLimitError,
)
from homeassistant.components.meraki_dashboard.coordinator import (
    RATE_LIMIT_ISSUE_ID,
    MerakiDashboardDataUpdateCoordinator,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_rate_limit_creates_issue_and_recovers(
    hass, mock_config_entry: MockConfigEntry
) -> None:
    """Test rate limit creates a repairs issue and is cleared on recovery."""
    api = Mock()
    api.async_get_network_clients = AsyncMock(
        side_effect=MerakiDashboardApiRateLimitError(2.0)
    )
    api.async_get_network_bluetooth_clients = AsyncMock(return_value=[])
    api.async_get_organization_devices_statuses = AsyncMock(return_value=[])

    coordinator = MerakiDashboardDataUpdateCoordinator(
        hass,
        mock_config_entry,
        api,
        track_clients=True,
        track_bluetooth_clients=False,
        track_infrastructure_devices=True,
        included_clients=set(),
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue("meraki_dashboard", RATE_LIMIT_ISSUE_ID)

    api.async_get_network_clients = AsyncMock(return_value=[])
    api.async_get_network_bluetooth_clients = AsyncMock(return_value=[])
    await coordinator._async_update_data()

    assert (
        issue_registry.async_get_issue("meraki_dashboard", RATE_LIMIT_ISSUE_ID) is None
    )
