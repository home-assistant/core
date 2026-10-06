"""Tests for Daikin Onecta diagnostics."""

from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from .test_climate_snapshots import _async_setup_fixture

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test cached cloud data is provided with identifying data redacted."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    config_entry.runtime_data.api.client.get_gateway_devices = AsyncMock()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["config_entry"]["data"]["token"] == REDACTED
    assert diagnostics["devices"]
    assert diagnostics["devices"][0]["id"] == REDACTED
    config_entry.runtime_data.api.client.get_gateway_devices.assert_not_awaited()
