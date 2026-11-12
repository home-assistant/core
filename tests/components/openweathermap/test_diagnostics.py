"""Tests for the diagnostics data provided by the OpenWeatherMap integration."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    OWM_MODE_AIRPOLLUTION,
    OWM_MODE_V30,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform


@pytest.mark.parametrize("mode", [OWM_MODE_V30, OWM_MODE_AIRPOLLUTION], indirect=True)
@pytest.mark.usefixtures("owm_client_mock")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_platform(hass, mock_config_entry, [Platform.WEATHER])
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
