"""Tests for the Bosch SHC sensor platform."""

from collections.abc import Generator
from unittest.mock import patch

from boschshcpy.services_impl import ValveTappetService
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration, thermostat_device

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the sensor platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "thermostats": [
                thermostat_device(valvestate=ValveTappetService.State.VALVE_TOO_TIGHT)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_valve_tappet_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A thermostat's valve motor status is exposed as an ENUM sensor."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.thermostat_valve_motor_status")
    assert state is not None
    assert state.state == "valve_too_tight"


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_valvetappet_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The raw valve tappet percentage sensor stays opt-in, superseded by the valve entity."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get("sensor.thermostat_valvetappet")
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
