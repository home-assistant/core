"""Test AirNow diagnostics."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("setup_airnow")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""

    # Fake LocalTimeZoneInfo
    with patch(
        "homeassistant.util.dt.async_get_time_zone",
        return_value="PST",
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        assert await get_diagnostics_for_config_entry(
            hass, hass_client, config_entry
        ) == snapshot(exclude=props("created_at", "modified_at"))
