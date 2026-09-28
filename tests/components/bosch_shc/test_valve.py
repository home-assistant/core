"""Tests for the Bosch SHC valve platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import setup_integration, thermostat_device

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the valve platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.VALVE]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device(position=42)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_valve_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A thermostat's valve tappet position is exposed as a valve entity."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.thermostat_valve")
    assert state is not None
    assert state.attributes["current_position"] == 42
