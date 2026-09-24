"""Tests for the Overkiz climate platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import OverkizState
from pyoverkiz.models import Event
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    assert_command_call,
    async_deliver_events,
    device_available_event,
    device_removed_event,
    device_state_changed_event,
    device_unavailable_event,
)

from tests.common import snapshot_platform

# io:HeatingValveIOComponent
VALVE = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#1",
    "climate.maple_residence_garden_radiator",
)
# modbuslink:AtlanticElectricalHeaterWithAdjustableTemperatureSetpointMBLComponent
COZYTOUCH = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "modbuslink://1234-5678-5643/1#1",
    "climate.living_room_heater",
)
# Atlantic Calissia (io:AtlanticElectricalHeaterWithAdjustableTemperatureSetpointIOComponent)
ELECTRICAL_HEATER_ADJUSTABLE = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/11009627#1",
    "climate.my_home_living_room_heater",
)

# Hitachi Yutaki 2-zone air-to-water heat pump
YUTAKI_ZONE_1 = FixtureDevice(
    "setup/cloud_hi_kumo_europe.json",
    "modbus://1234-5678-2284/5416194/1#2",
    "climate.somfy_tahoma_switch_yutaki_zone_1",
)
YUTAKI_ZONE_2 = FixtureDevice(
    "setup/cloud_hi_kumo_europe.json",
    "modbus://1234-5678-2284/5416194/1#3",
    "climate.somfy_tahoma_switch_yutaki_zone_2",
)
# io:HeatingThermostatIOComponent
THERMOSTAT_HEATING = FixtureDevice(
    "setup/cloud_somfy_tahoma_switch_sc_europe.json",
    "io://1234-5678-5010/386310#1",
    "climate.study_thermostat",
)

SNAPSHOT_FIXTURES = [
    VALVE,
    COZYTOUCH,
    YUTAKI_ZONE_1,
    THERMOSTAT_HEATING,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to climate only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_valve_hvac_action_none_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test that hvac_action handles None valve state without crashing."""
    await setup_overkiz_integration(fixture=VALVE.fixture)

    state = hass.states.get(VALVE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE

    # Deliver an event that clears the valve state
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=VALVE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_OPEN_CLOSED_VALVE,
                        "type": 3,
                        "value": None,
                    }
                ],
            )
        ],
    )

    # hvac_action should be None (unknown) rather than raising KeyError
    state = hass.states.get(VALVE.entity_id)
    assert state is not None
    assert state.attributes.get(ATTR_HVAC_ACTION) is None


UNKNOWN_DEVICE_URL = "zigbee://1234-5678-1698/65535"


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(device_available_event(UNKNOWN_DEVICE_URL), id="available"),
        pytest.param(device_unavailable_event(UNKNOWN_DEVICE_URL), id="unavailable"),
        pytest.param(
            device_state_changed_event(
                UNKNOWN_DEVICE_URL,
                [{"name": "core:OnOffState", "type": 3, "value": "on"}],
            ),
            id="state_changed",
        ),
        pytest.param(device_removed_event(UNKNOWN_DEVICE_URL), id="removed"),
    ],
)
async def test_events_for_unknown_device_url(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    event: Event,
) -> None:
    """Test that events for unknown device URLs don't crash the coordinator."""
    await setup_overkiz_integration(fixture=VALVE.fixture)

    await async_deliver_events(hass, freezer, mock_client, [event])

    # Should not crash; valve entity should still be available
    state = hass.states.get(VALVE.entity_id)
    assert state is not None


async def test_electrical_heater_adjustable_target_temperature(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test target_temperature tracks the effective setpoint only in auto mode."""
    await setup_overkiz_integration(fixture=ELECTRICAL_HEATER_ADJUSTABLE.fixture)

    # Fixture starts in auto (external) mode with the eco preset active.
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 16.5

    # The preset changes to comfort while still scheduled (auto).
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_TARGET_HEATING_LEVEL,
                        "type": 3,
                        "value": "comfort",
                    },
                    {
                        "name": OverkizState.IO_EFFECTIVE_TEMPERATURE_SETPOINT,
                        "type": 2,
                        "value": 20.0,
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 20.0

    # While scheduled (auto), setting a temperature derogates the active
    # preset instead of overwriting the comfort setpoint.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ELECTRICAL_HEATER_ADJUSTABLE.entity_id, ATTR_TEMPERATURE: 19.0},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
        command_name="setDerogatedTargetTemperature",
        parameters=[19.0],
    )

    # The device reports the derogation by updating the effective setpoint.
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_EFFECTIVE_TEMPERATURE_SETPOINT,
                        "type": 2,
                        "value": 19.0,
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 19.0

    mock_client.execute_action_group.reset_mock()

    # Leaving auto (scheduled) mode for manual falls back to
    # core:TargetTemperatureState, and setting a temperature now targets
    # that state directly instead of derogating.
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_OPERATING_MODE,
                        "type": 3,
                        "value": "manual",
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 20.0

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ELECTRICAL_HEATER_ADJUSTABLE.entity_id, ATTR_TEMPERATURE: 21.0},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
        command_name="setTargetTemperature",
        parameters=[21.0],
    )

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_TARGET_TEMPERATURE,
                        "type": 2,
                        "value": 21.0,
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 21.0


async def test_hitachi_air_to_water_heating_zone_2(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the second heating zone reads its own Zone2 states."""
    await setup_overkiz_integration(fixture=YUTAKI_ZONE_2.fixture)

    zone_1 = hass.states.get(YUTAKI_ZONE_1.entity_id)
    assert zone_1 is not None
    assert zone_1.attributes[ATTR_CURRENT_TEMPERATURE] == 18.5

    zone_2 = hass.states.get(YUTAKI_ZONE_2.entity_id)
    assert zone_2 is not None
    assert zone_2.state == HVACMode.AUTO
    assert zone_2.attributes[ATTR_CURRENT_TEMPERATURE] == 20.5
    assert zone_2.attributes[ATTR_TEMPERATURE] == 21.0


async def test_thermostat_heating_set_temperature(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test setting a temperature issues setDerogation, not setComfortTemperature."""
    await setup_overkiz_integration(fixture=THERMOSTAT_HEATING.fixture)

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": THERMOSTAT_HEATING.entity_id, ATTR_TEMPERATURE: 20.0},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=THERMOSTAT_HEATING.device_url,
        command_name="setDerogation",
        parameters=[20.0, "further_notice"],
    )


@pytest.mark.parametrize(
    ("preset_mode", "parameters"),
    [
        pytest.param("away", ["away", "further_notice"], id="away"),
        pytest.param("comfort", ["comfort", "further_notice"], id="comfort"),
        pytest.param("eco", ["eco", "further_notice"], id="eco"),
        # Manual re-sends the current temperature to enter the derogation
        pytest.param("manual", [26.6, "further_notice"], id="manual"),
    ],
)
async def test_thermostat_heating_set_preset_mode(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    preset_mode: str,
    parameters: list[str | float],
) -> None:
    """Test selecting a preset issues setDerogation with the mapped parameter."""
    await setup_overkiz_integration(fixture=THERMOSTAT_HEATING.fixture)

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": THERMOSTAT_HEATING.entity_id, ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=THERMOSTAT_HEATING.device_url,
        command_name="setDerogation",
        parameters=parameters,
    )
