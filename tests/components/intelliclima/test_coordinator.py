"""Test the IntelliClima coordinators."""

from unittest.mock import AsyncMock

from pyintelliclima.api import IntelliClimaAPIError
from pyintelliclima.intelliclima_types import IntelliClimaFilterStatus

from homeassistant.components.intelliclima.coordinator import (
    IntelliClimaFilterCoordinator,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_filter_coordinator_isolates_per_device_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failure fetching one device's filter status must not drop other devices."""
    mock_config_entry.add_to_hass(hass)
    api = AsyncMock()
    api.get_filter_status.side_effect = [
        IntelliClimaFilterStatus(
            serial="AAA",
            is_active=True,
            from_date="2026-08-04 00:00:00",
            stats=[],
            totale=0,
            change_filter=False,
        ),
        IntelliClimaAPIError("boom"),
    ]
    coordinator = IntelliClimaFilterCoordinator(
        hass, mock_config_entry, api, ["AAA", "BBB"]
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert "AAA" in coordinator.data
    assert "BBB" not in coordinator.data
