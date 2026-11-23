"""Test Waze Travel Time diagnostics."""

import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.waze_travel_time.const import (
    CONF_BASE_COORDINATES,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    DEFAULT_OPTIONS,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG


@pytest.mark.parametrize(
    ("data", "options"),
    [
        pytest.param(
            MOCK_CONFIG,
            {
                **DEFAULT_OPTIONS,
                CONF_INCL_FILTER: ["IncludeThis"],
                CONF_EXCL_FILTER: ["ExcludeThis"],
                CONF_BASE_COORDINATES: {CONF_LATITUDE: 52.52, CONF_LONGITUDE: 13.4},
            },
            id="filters_and_base_coordinates",
        )
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = hass.config_entries.async_get_entry("test")
    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
