"""Tests for the Overkiz sensor platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import MeasuredValueType, OverkizAttribute, OverkizState
import pytest
from pytest_homeassistant.common import snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    async_deliver_events,
    device_state_changed_event,
    device_unavailable_event,
)

TEMPERATURE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#2",
    "sensor.maple_residence_garden_radiator_bathroom_temperature_sensor_temperature",
)
HEATING_BATTERY = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#1",
    "sensor.maple_residence_garden_radiator_battery_level",
)
TEMPERATURE_SENSOR_LOCAL = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_3.json",
    "io://1234-5678--9373/1292684#2",
    "sensor.garden_temperature_sensor_temperature",
)
HOMEKIT_STACK = FixtureDevice(
    "setup/cloud_somfy_tahoma_switch_europe.json",
    "homekit://1234-5678-6867/stack",
    "sensor.tahoma_switch_homekit_setup_code",
)
# Device with core:MeasuredValueType attribute (test for dynamic unit resolution)
COZYTOUCH_DHW = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/109286#2",
    "sensor.my_home_patio_water_heating_office_energy_meter_electric_energy_consumption",
)
HEATING_DISCRETE_RSSI = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#1",
    "sensor.maple_residence_garden_radiator_discrete_rssi_level",
)
DHW_HEAT_PUMP_OPERATING_TIME = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/6713703#1",
    "sensor.my_home_water_heater_heat_pump_operating_time",
)
# Atlantic heater exposing core:ErrorCodeState (0 means no fault)
COZYTOUCH_ERROR_CODE = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "modbuslink://1234-5678-5643/1#1",
    "sensor.living_room_heater_error_code",
)
# Hitachi Yutaki heat pump exposing energy and temperature sensors
YUTAKI = FixtureDevice(
    "setup/cloud_hi_kumo_europe.json",
    "modbus://1234-5678-2284/5416194/1#1",
    "sensor.my_house_yutaki_outdoor_ambient_temperature",
)

SNAPSHOT_FIXTURES = [
    TEMPERATURE_SENSOR,
    TEMPERATURE_SENSOR_LOCAL,
    HOMEKIT_STACK,
    COZYTOUCH_DHW,
    YUTAKI,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to sensor only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_sensor_temperature_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for a float sensor (temperature 24.4 → 22.1)."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert state
    assert state.state == "24.4"

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=TEMPERATURE_SENSOR.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_TEMPERATURE.value,
                        "type": 2,
                        "value": 22.1,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert state.state == "22.1"


async def test_sensor_battery_level_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for an integer sensor (battery 59 → 42)."""
    await setup_overkiz_integration(fixture=HEATING_BATTERY.fixture)

    state = hass.states.get(HEATING_BATTERY.entity_id)
    assert state
    assert state.state == "59"

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=HEATING_BATTERY.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_BATTERY_LEVEL.value,
                        "type": 2,
                        "value": 42.0,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(HEATING_BATTERY.entity_id)
    assert state.state == "42"


@pytest.mark.parametrize(
    ("device", "state_name", "state_type", "value", "expected"),
    [
        pytest.param(
            TEMPERATURE_SENSOR,
            OverkizState.CORE_TEMPERATURE,
            2,
            0.0,
            "0.0",
            id="measurement",
        ),
        pytest.param(
            COZYTOUCH_DHW,
            OverkizState.CORE_ELECTRIC_ENERGY_CONSUMPTION,
            1,
            0,
            "0",
            id="total_increasing",
        ),
        pytest.param(
            DHW_HEAT_PUMP_OPERATING_TIME,
            OverkizState.IO_HEAT_PUMP_OPERATING_TIME,
            1,
            0,
            "0",
            id="no_state_class",
        ),
        pytest.param(
            HEATING_DISCRETE_RSSI,
            OverkizState.CORE_DISCRETE_RSSI_LEVEL,
            3,
            "",
            STATE_UNKNOWN,
            id="empty_string_enum",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_falsy_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    device: FixtureDevice,
    state_name: OverkizState,
    state_type: int,
    value: float | str,
    expected: str,
) -> None:
    """Test falsy values: 0 is a valid state, an empty string is unknown."""
    await setup_overkiz_integration(fixture=device.fixture)

    state = hass.states.get(device.entity_id)
    assert state
    assert state.state not in (expected, STATE_UNKNOWN)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=device.device_url,
                device_states=[
                    {"name": state_name.value, "type": state_type, "value": value},
                ],
            )
        ],
    )

    state = hass.states.get(device.entity_id)
    assert state
    assert state.state == expected


async def test_sensor_dynamic_unit_with_zero_value(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the device-reported unit is used when the value is 0."""
    await setup_overkiz_integration(fixture=COZYTOUCH_DHW.fixture)

    state = hass.states.get(COZYTOUCH_DHW.entity_id)
    assert state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.WATT_HOUR

    # The unit is resolved on every state write, so switching the device's
    # reported unit after setup is picked up by the next event
    device = next(
        device
        for device in mock_client.setup.devices
        if device.device_url == COZYTOUCH_DHW.device_url
    )
    device.attributes[
        OverkizAttribute.CORE_MEASURED_VALUE_TYPE
    ].value = MeasuredValueType.ELECTRICAL_ENERGY_IN_KWH

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=COZYTOUCH_DHW.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_ELECTRIC_ENERGY_CONSUMPTION.value,
                        "type": 1,
                        "value": 0,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(COZYTOUCH_DHW.entity_id)
    assert state
    assert state.state == "0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR


async def test_sensor_error_code_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test error code reports a fault and its clearing (0 → 370 → 0)."""
    await setup_overkiz_integration(fixture=COZYTOUCH_ERROR_CODE.fixture)

    state = hass.states.get(COZYTOUCH_ERROR_CODE.entity_id)
    assert state
    assert state.state == "0"

    for value in (370, 0):
        await async_deliver_events(
            hass,
            freezer,
            mock_client,
            [
                device_state_changed_event(
                    device_url=COZYTOUCH_ERROR_CODE.device_url,
                    device_states=[
                        {
                            "name": OverkizState.CORE_ERROR_CODE.value,
                            "type": 1,
                            "value": value,
                        },
                    ],
                )
            ],
        )

        state = hass.states.get(COZYTOUCH_ERROR_CODE.entity_id)
        assert state.state == str(value)


async def test_sensor_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_unavailable_event(
                device_url=TEMPERATURE_SENSOR.device_url,
            )
        ],
    )

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
