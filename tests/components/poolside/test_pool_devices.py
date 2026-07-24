"""Tests for pool device sub-devices and their InformationFields sensors."""

import json

import pytest

from homeassistant.components.poolside.client import PoolsideCommandError
from homeassistant.components.poolside.const import DOMAIN
from homeassistant.components.poolside.models import PoolsideDevice
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import TEST_CONTROLLER_UUID, FakePoolsideClient

from tests.common import MockConfigEntry

PUMP_UUID = "device-pump-1"

MODE_ENTITY_ID = "sensor.test_residence_controller_mode"
POWER_ENTITY_ID = "sensor.pump_power"

# The pump descriptor observed on the wire, trimmed to the keys the
# integration reads plus one control-typed entry that must be skipped.
INFORMATION_FIELDS = json.dumps(
    [
        {
            "Name": "Watts",
            "DisplayName": "Power",
            "DisplayOrder": 1,
            "DisplayProcessingLogic": "WATTAGE",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "RPM",
            "DisplayName": "RPM",
            "DisplayOrder": 2,
            "DisplayProcessingLogic": "RPM",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "GPM",
            "DisplayName": "Flow",
            "DisplayOrder": 3,
            "DisplayProcessingLogic": "GPM",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "PSI",
            "DisplayName": "Pressure",
            "DisplayOrder": 4,
            "DisplayProcessingLogic": "PSI",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "PumpState",
            "DisplayName": "Status",
            "DisplayOrder": 5,
            "DisplayProcessingLogic": "LONG_STRING",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "CoolingDownUntil",
            "DisplayName": "Heater Cooldown Until",
            "DisplayOrder": 7,
            "DisplayProcessingLogic": "DATETIME",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "Vibration",
            "DisplayName": "Vibration",
            "DisplayOrder": 8,
            "DisplayProcessingLogic": "SPARKLINE",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "TargetSpeed",
            "DisplayName": "Target Speed",
            "DisplayOrder": 9,
            "DisplayProcessingLogic": "PERCENT",
            "FieldTypes": ["CONTROL"],
        },
    ]
)


@pytest.fixture
def pool_devices() -> list[PoolsideDevice]:
    """One pump, as returned by Site.getPoolDevices."""
    return [PoolsideDevice(uuid=PUMP_UUID, device_type="Pump")]


async def setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the config entry and settle."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_created_from_initial_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Each INFORMATION field becomes a sensor; control-typed fields do not."""
    mock_poolside_client.set_status(PUMP_UUID, "InformationFields", INFORMATION_FIELDS)
    await setup_entry(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids("sensor")) == {
        MODE_ENTITY_ID,
        POWER_ENTITY_ID,
        "sensor.pump_rpm",
        "sensor.pump_flow",
        "sensor.pump_pressure",
        "sensor.pump_status",
        "sensor.pump_heater_cooldown_until",
        "sensor.pump_vibration",
    }


@pytest.mark.parametrize(
    ("field", "entity_id", "raw_value", "expected_state", "expected_unit"),
    [
        pytest.param("Watts", POWER_ENTITY_ID, "1250", "1250.0", "W", id="wattage"),
        pytest.param(
            "Watts", POWER_ENTITY_ID, "banana", STATE_UNKNOWN, "W", id="wattage-garbage"
        ),
        pytest.param("RPM", "sensor.pump_rpm", "2850", "2850.0", "rpm", id="rpm"),
        pytest.param("GPM", "sensor.pump_flow", "55", "55.0", "gal/min", id="gpm"),
        pytest.param("PSI", "sensor.pump_pressure", "12.4", "12.4", "psi", id="psi"),
        pytest.param(
            "PumpState",
            "sensor.pump_status",
            "PRIMING",
            "PRIMING",
            None,
            id="long-string",
        ),
        pytest.param(
            "CoolingDownUntil",
            "sensor.pump_heater_cooldown_until",
            "2026-07-22T15:30:00+00:00",
            "2026-07-22T15:30:00+00:00",
            None,
            id="datetime",
        ),
        pytest.param(
            # The test harness's local timezone is US/Pacific (UTC-7 in July).
            "CoolingDownUntil",
            "sensor.pump_heater_cooldown_until",
            "2026-07-22T15:30:00",
            "2026-07-22T22:30:00+00:00",
            None,
            id="datetime-naive-assumed-local",
        ),
        pytest.param(
            "CoolingDownUntil",
            "sensor.pump_heater_cooldown_until",
            "not-a-date",
            STATE_UNKNOWN,
            None,
            id="datetime-garbage",
        ),
        pytest.param(
            "Vibration",
            "sensor.pump_vibration",
            "42",
            "42",
            None,
            id="unrecognized-logic-renders-as-text",
        ),
    ],
)
async def test_field_value_rendering(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    field: str,
    entity_id: str,
    raw_value: str,
    expected_state: str,
    expected_unit: str | None,
) -> None:
    """Values render per the field's DisplayProcessingLogic, with the right unit.

    Uses imperial units so the psi native unit matches the test hass's unit
    system and needs no conversion.
    """
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_poolside_client.set_status(PUMP_UUID, "InformationFields", INFORMATION_FIELDS)
    mock_poolside_client.set_status(PUMP_UUID, field, raw_value)
    await setup_entry(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit


@pytest.mark.usefixtures("setup_integration")
async def test_sensors_added_when_information_fields_arrive_later(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """A device with no snapshot grows its sensors when the descriptor is pushed."""
    assert hass.states.get(POWER_ENTITY_ID) is None

    fake_client.set_status(PUMP_UUID, "InformationFields", INFORMATION_FIELDS)
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(PUMP_UUID, "Watts", "900")
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "900.0"


async def test_pool_device_registered_under_controller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The pool device exists even before any telemetry, linked via the controller."""
    await setup_entry(hass, mock_config_entry)

    controller = device_registry.async_get_device({(DOMAIN, TEST_CONTROLLER_UUID)})
    assert controller is not None
    device = device_registry.async_get_device({(DOMAIN, PUMP_UUID)})
    assert device is not None
    assert device.via_device_id == controller.id
    assert device.manufacturer == "Poolside"
    assert device.model == "Pump"
    assert device.name == "Pump"


async def test_pool_device_named_from_streamed_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A streamed Name state wins over the DeviceType fallback."""
    mock_poolside_client.set_status(PUMP_UUID, "Name", "Main Pump")
    await setup_entry(hass, mock_config_entry)

    device = device_registry.async_get_device({(DOMAIN, PUMP_UUID)})
    assert device is not None
    assert device.name == "Main Pump"


async def test_setup_succeeds_without_pool_device_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Firmware without Site.getPoolDevices loads normally with no pool devices."""
    mock_poolside_client.async_get_pool_devices.side_effect = PoolsideCommandError(
        "unknown method"
    )
    await setup_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.pool_devices == []
