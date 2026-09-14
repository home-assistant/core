"""Tests for the Bosch SHC sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy.services_impl import ValveTappetService
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import setup_integration, thermostat_device

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the sensor platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("mock_session")
async def test_open_windows_doors_sensor(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The whole-home open-doors/open-windows summary is exposed and polled."""
    mock_session.api.get_open_windows.return_value = {
        "openDoors": [{"name": "Front Door"}],
        "openWindows": [{"name": "Kitchen Window"}, {"name": "Bedroom Window"}],
        "openOthers": [{"name": "Cat Flap"}],
    }
    await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.mock_title_open_doors_and_windows"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "4"
    assert state.attributes["open_doors"] == ["Front Door"]
    assert state.attributes["open_windows"] == ["Kitchen Window", "Bedroom Window"]
    assert state.attributes["open_others"] == ["Cat Flap"]

    hub_device = device_registry.async_get_device_by_identifier(
        ("bosch_shc", "test-mac"), mock_config_entry.entry_id
    )
    assert hub_device is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.device_id == hub_device.id

    mock_session.api.get_open_windows.return_value = {
        "openDoors": [],
        "openWindows": [],
        "openOthers": [],
    }
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"


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
