"""Test Matter locks."""

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.client.exceptions import InvalidState, ServerVersionTooOld
from matter_server.client.models.node import MatterNode
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import (
    create_attribute_path_from_attribute,
    dataclass_to_tag_dict,
)
from matter_server.common.models import InteractionReport
import pytest
from pytest_homeassistant.common import mock_restore_cache_with_extra_data
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.matter.const import (
    ATTR_COOLING_SETPOINT,
    ATTR_HEATING_SETPOINT,
    ATTR_PRESET_NAME,
    ATTR_PRESET_SCENARIO,
    DOMAIN,
)
from homeassistant.components.matter.thermostat_helpers import (
    InvalidPresetDataError,
    _validate_unique_preset_name,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform, TargetKey
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import (
    load_and_parse_node_fixture,
    set_node_attribute,
    setup_integration_with_node_fixture,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

THERMOSTAT_ENTITY_ID = "climate.longan_link_hvac"
ROOM_AC_ENTITY_ID = "climate.room_airconditioner"
EVE_THERMO_ENTITY_ID = "climate.eve_thermo_20ecd1701"
THERMOSTAT_CLUSTER_ID = 513
PRESETS_ATTRIBUTE_ID = 80
PRESETS_ATTRIBUTE_PATH = "1/513/80"
THERMOSTAT_CLUSTER_PATH = "1/513"
# The eve_thermo_v5 PresetTypes, with room for a second `occupied` preset
TWO_OCCUPIED_PRESET_TYPES = [
    {"0": 1, "1": 2, "2": 2},
    {"0": 2, "1": 1, "2": 2},
    {"0": 3, "1": 1, "2": 2},
    {"0": 4, "1": 1, "2": 2},
    {"0": 5, "1": 1, "2": 2},
    {"0": 6, "1": 1, "2": 2},
    {"0": 254, "1": 1, "2": 2},
]


def _eve_thermo_presets() -> list[clusters.Thermostat.Structs.PresetStruct]:
    """Return the eve_thermo_v5 fixture's Presets attribute, decoded."""
    return [
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\x01",
            presetScenario=1,
            name="Home",
            coolingSetpoint=None,
            heatingSetpoint=2200,
            builtIn=True,
        ),
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\x02",
            presetScenario=2,
            name="Away",
            coolingSetpoint=None,
            heatingSetpoint=1800,
            builtIn=True,
        ),
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\x03",
            presetScenario=3,
            name="Sleep",
            coolingSetpoint=None,
            heatingSetpoint=2000,
            builtIn=False,
        ),
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\x04",
            presetScenario=4,
            name="Wake",
            coolingSetpoint=None,
            heatingSetpoint=2300,
            builtIn=False,
        ),
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\x05",
            presetScenario=5,
            name="Vacation",
            coolingSetpoint=None,
            heatingSetpoint=1600,
            builtIn=False,
        ),
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\x06",
            presetScenario=6,
            name="GoingToSleep",
            coolingSetpoint=None,
            heatingSetpoint=2100,
            builtIn=False,
        ),
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\xfe",
            presetScenario=254,
            name="Eco",
            coolingSetpoint=None,
            heatingSetpoint=1600,
            builtIn=False,
        ),
    ]


@pytest.mark.parametrize(
    ("presets", "scenario", "name", "exclude_handle", "raises"),
    [
        # Duplicate name in the same scenario.
        ([(1, "Home")], 1, "Home", None, True),
        # Same name in a different scenario.
        ([(2, "Home")], 1, "Home", None, False),
        # Null names are also unique within a scenario.
        ([(1, None)], 1, None, None, True),
        # The preset being edited must be excluded.
        ([(1, "Home", b"\x01")], 1, "Home", b"\x01", False),
        # Another preset with the same name must still be detected.
        (
            [(1, "Home", b"\x01"), (1, "Away", b"\x02")],
            1,
            "Away",
            b"\x01",
            True,
        ),
    ],
)
def test_validate_unique_preset_name(
    presets: list[tuple],
    scenario: int,
    name: str | None,
    exclude_handle: bytes | None,
    raises: bool,
) -> None:
    """Validate preset name uniqueness within a scenario."""
    current_presets = [
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=(preset[2] if len(preset) == 3 else bytes([index + 1])),
            presetScenario=preset[0],
            name=preset[1],
            coolingSetpoint=None,
            heatingSetpoint=2000,
            builtIn=False,
        )
        for index, preset in enumerate(presets)
    ]

    if raises:
        with pytest.raises(InvalidPresetDataError):
            _validate_unique_preset_name(
                current_presets, scenario, name, exclude_handle
            )
    else:
        _validate_unique_preset_name(current_presets, scenario, name, exclude_handle)


def _wire_presets(
    presets: list[clusters.Thermostat.Structs.PresetStruct],
) -> list[dict[str, Any]]:
    """Return presets in the tag-keyed wire format the client's read returns."""
    return [
        {
            **dataclass_to_tag_dict(preset),
            "0": base64.b64encode(preset.presetHandle).decode(),
        }
        for preset in presets
    ]


def _mock_preset_write(
    matter_client: MagicMock,
    current_presets: list[clusters.Thermostat.Structs.PresetStruct] | None = None,
    data_version: int = 1,
    endpoint_id: int = 1,
) -> None:
    """Mock a successful read + write_atomic_attribute round trip."""
    presets_path = f"{endpoint_id}/{THERMOSTAT_CLUSTER_ID}/{PRESETS_ATTRIBUTE_ID}"
    matter_client.read = AsyncMock(
        return_value=InteractionReport(
            attributes={
                presets_path: _wire_presets(
                    current_presets
                    if current_presets is not None
                    else _eve_thermo_presets()
                )
            },
            events=[],
            data_versions={f"{endpoint_id}/{THERMOSTAT_CLUSTER_ID}": data_version},
        )
    )
    matter_client.write_atomic_attribute = AsyncMock(return_value=[{"Status": 0}])


def _thermostat_on_endpoint_2() -> dict[str, Any]:
    """Return attribute overrides that duplicate the eve thermostat onto endpoint 2."""
    attributes = load_and_parse_node_fixture("eve_thermo_v5")["attributes"]
    overrides = {
        f"2{path[1:]}": value
        for path, value in attributes.items()
        if path.startswith("1/")
    }
    overrides["0/29/3"] = [1, 2]
    overrides["2/513/72"] = TWO_OCCUPIED_PRESET_TYPES
    return overrides


@pytest.fixture
def platform() -> Platform:
    """Return the platform under test."""
    return Platform.CLIMATE


@pytest.mark.usefixtures("matter_devices")
async def test_climates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climates."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.CLIMATE)


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_thermostat_base(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat base attributes and state updates."""
    # test entity attributes
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["min_temp"] == 7
    assert state.attributes["max_temp"] == 35
    assert state.attributes["temperature"] is None
    assert state.state == HVACMode.COOL

    # test supported features correctly parsed
    # including temperature_range support
    mask = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    assert state.attributes["supported_features"] & mask == mask

    # test common state updates from device
    set_node_attribute(matter_node, 1, 513, 3, 1600)
    set_node_attribute(matter_node, 1, 513, 4, 3000)
    set_node_attribute(matter_node, 1, 513, 5, 1600)
    set_node_attribute(matter_node, 1, 513, 6, 3000)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["min_temp"] == 16
    assert state.attributes["max_temp"] == 30
    assert state.attributes["hvac_modes"] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    ]

    # test system mode update from device
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.OFF

    # test running state update from device
    set_node_attribute(matter_node, 1, 513, 41, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(matter_node, 1, 513, 41, 5)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(matter_node, 1, 513, 41, 8)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(matter_node, 1, 513, 41, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 6)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 16)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 66)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 4)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 32)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 64)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 128)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.OFF

    # running state 0 (idle) must not be treated as a missing attribute;
    # with the system mode off this maps to hvac_action "off"
    set_node_attribute(matter_node, 1, 513, 41, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.OFF

    # change system mode to heat
    set_node_attribute(matter_node, 1, 513, 28, 4)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT

    # running state 0 (no relay active) while the system mode is on
    # means the device is idle
    set_node_attribute(matter_node, 1, 513, 41, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.IDLE

    # change occupied heating setpoint to 20
    set_node_attribute(matter_node, 1, 513, 18, 2000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["temperature"] == 20


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_thermostat_humidity(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat humidity attribute and state updates."""
    # test entity attributes
    state = hass.states.get("climate.longan_link_hvac")
    assert state

    measured_value = clusters.RelativeHumidityMeasurement.Attributes.MeasuredValue

    # test current humidity update from device
    set_node_attribute(
        matter_node,
        1,
        measured_value.cluster_id,
        measured_value.attribute_id,
        1234,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["current_humidity"] == 12.34

    # test current humidity update from device with zero value
    set_node_attribute(
        matter_node,
        1,
        measured_value.cluster_id,
        measured_value.attribute_id,
        0,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["current_humidity"] == 0.0

    # test current humidity update from device with None value
    set_node_attribute(
        matter_node,
        1,
        measured_value.cluster_id,
        measured_value.attribute_id,
        None,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert "current_humidity" not in state.attributes


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_thermostat_service_calls(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test climate platform service calls."""
    # test single-setpoint temperature adjustment when cool mode is active
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.COOL
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 25,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=2500,
    )
    matter_client.write_attribute.reset_mock()

    # ensure that no command is executed when the temperature is the same
    set_node_attribute(matter_node, 1, 513, 17, 2500)
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 25,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 0
    matter_client.write_attribute.reset_mock()

    # test single-setpoint temperature adjustment when heat mode is active
    set_node_attribute(matter_node, 1, 513, 28, 4)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 20,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/18",
        value=2000,
    )
    matter_client.write_attribute.reset_mock()

    # test dual setpoint temperature adjustments when heat_cool mode is active
    set_node_attribute(matter_node, 1, 513, 28, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT_COOL

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "target_temp_low": 10,
            "target_temp_high": 30,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/18",
        value=1000,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=3000,
    )
    matter_client.write_attribute.reset_mock()

    # test changing only target_temp_high when target_temp_low stays the same
    set_node_attribute(matter_node, 1, 513, 18, 1000)
    set_node_attribute(matter_node, 1, 513, 17, 2500)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["target_temp_high"] == 25
    assert state.attributes["target_temp_low"] == 10

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "target_temp_low": 10,  # Same as current
            "target_temp_high": 28,  # Different from current
        },
        blocking=True,
    )

    # Only target_temp_high should be written since target_temp_low hasn't changed
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=2800,
    )
    matter_client.write_attribute.reset_mock()

    # test change HAVC mode to heat
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            "entity_id": "climate.longan_link_hvac",
            "hvac_mode": HVACMode.HEAT,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=4,
    )
    matter_client.send_device_command.reset_mock()

    # change target_temp and hvac_mode in the same call
    matter_client.send_device_command.reset_mock()
    matter_client.write_attribute.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 22,
            "hvac_mode": HVACMode.COOL,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=3,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=2200,
    )
    matter_client.write_attribute.reset_mock()

    # fractional setpoints must round, not truncate: 10.2 * 100 is 1019.9999…
    # in IEEE 754, so int() would produce 1019 instead of 1020.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 10.2,
            "hvac_mode": HVACMode.HEAT,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_args_list[-1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/18",
        value=1020,
    )
    matter_client.write_attribute.reset_mock()


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
async def test_room_airconditioner(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test if a climate entity is created for a Room Airconditioner device."""
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.attributes["current_temperature"] == 20
    # room airconditioner has mains power on OnOff cluster with value set to False
    assert state.state == HVACMode.OFF

    # test supported features correctly parsed
    # WITHOUT temperature_range support
    mask = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF
    assert state.attributes["supported_features"] & mask == mask

    # set mains power to ON (OnOff cluster)
    set_node_attribute(matter_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")

    # test supported HVAC modes include fan and dry modes
    assert state.attributes["hvac_modes"] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT_COOL,
    ]
    # test fan-only hvac mode
    set_node_attribute(matter_node, 1, 513, 28, 7)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.state == HVACMode.FAN_ONLY

    # test dry hvac mode
    set_node_attribute(matter_node, 1, 513, 28, 8)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.state == HVACMode.DRY

    # test featuremap update
    set_node_attribute(matter_node, 1, 513, 65532, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state.attributes["supported_features"] & ClimateEntityFeature.TURN_ON


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_eve_thermo_v5_presets(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Eve Thermo v5 thermostat presets attributes and state updates."""
    # test entity attributes
    entity_id = "climate.eve_thermo_20ecd1701"
    state = hass.states.get(entity_id)
    assert state

    # the Eve Thermo reports ThermostatRunningState 0 (no relay active);
    # this is a valid state and must be exposed as hvac_action idle
    # instead of being treated as a missing attribute
    assert state.attributes["hvac_action"] == HVACAction.IDLE

    # test supported features correctly parsed
    mask = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.PRESET_MODE
    )
    assert state.attributes["supported_features"] & mask == mask

    # Test preset modes parsed correctly from Eve Thermo v5
    # Should use HA standard presets for known ones, original names for others
    # PRESET_NONE is always included to allow users to clear the preset
    assert state.attributes["preset_modes"] == [
        "home",
        "away",
        "sleep",
        "wake",
        "vacation",
        "going_to_sleep",
        "Eco",
        PRESET_NONE,
    ]
    assert state.attributes["preset_mode"] == "home"

    # Get presets from the node for dynamic testing
    presets_attribute = matter_node.endpoints[1].get_attribute_value(
        513,
        clusters.Thermostat.Attributes.Presets.attribute_id,
    )
    preset_by_name = {preset.name: preset.presetHandle for preset in presets_attribute}

    # test set_preset_mode with "home" preset (HA standard)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "home",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(
            presetHandle=preset_by_name["Home"]
        ),
    )
    # Verify preset_mode is optimistically updated
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "home"
    matter_client.send_device_command.reset_mock()

    # test set_preset_mode with "away" preset (HA standard)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "away",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(
            presetHandle=preset_by_name["Away"]
        ),
    )
    # Verify preset_mode is optimistically updated
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "away"
    matter_client.send_device_command.reset_mock()

    # test set_preset_mode with "eco" preset (custom, device-provided name)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "Eco",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(
            presetHandle=preset_by_name["Eco"]
        ),
    )
    matter_client.send_device_command.reset_mock()

    # test set_preset_mode with invalid preset mode
    # The climate platform validates preset modes before calling our method

    # Get current state to derive expected modes
    state = hass.states.get(entity_id)
    assert state
    expected_modes = ", ".join(state.attributes["preset_modes"])

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {
                "entity_id": entity_id,
                "preset_mode": "InvalidPreset",
            },
            blocking=True,
        )

    assert err.value.translation_key == "not_valid_preset_mode"
    assert err.value.translation_placeholders == {
        "mode": "InvalidPreset",
        "modes": expected_modes,
    }

    # Ensure no command was sent for invalid preset
    assert matter_client.send_device_command.call_count == 0
    # Test that preset_mode is updated when ActivePresetHandle is set from device
    set_node_attribute(
        matter_node,
        1,
        513,
        clusters.Thermostat.Attributes.ActivePresetHandle.attribute_id,
        preset_by_name["Home"],
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "home"

    # Test preset_mode updates when ActivePresetHandle changes
    set_node_attribute(
        matter_node,
        1,
        513,
        clusters.Thermostat.Attributes.ActivePresetHandle.attribute_id,
        preset_by_name["Away"],
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "away"

    # Test that preset_mode is PRESET_NONE when ActivePresetHandle is cleared
    set_node_attribute(
        matter_node,
        1,
        513,
        clusters.Thermostat.Attributes.ActivePresetHandle.attribute_id,
        None,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == PRESET_NONE

    # Test that users can set preset_mode to PRESET_NONE to clear the active preset
    matter_client.send_device_command.reset_mock()
    # First set a preset so we have something to clear
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "home",
        },
        blocking=True,
    )
    matter_client.send_device_command.reset_mock()

    # Now call set_preset_mode with PRESET_NONE to clear it
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": PRESET_NONE,
        },
        blocking=True,
    )

    # Verify the command was sent with null value to clear the preset
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(presetHandle=None),
    )
    # Verify preset_mode is optimistically updated to PRESET_NONE
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == PRESET_NONE


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_preset_mode_with_unnamed_preset(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test preset mode when a preset has no name or empty name.

    This tests the fallback preset naming case where a preset does not have
    a mapped presetScenario and also has no device-provided name, requiring
    the fallback Preset{i} naming pattern.
    """
    entity_id = "climate.eve_thermo_20ecd1701"

    # Get current presets from the node
    presets_attribute = matter_node.endpoints[1].get_attribute_value(
        513,
        clusters.Thermostat.Attributes.Presets.attribute_id,
    )

    assert presets_attribute is not None

    # Add a new preset with unmapped scenario (e.g., 255) and no name
    new_preset = clusters.Thermostat.Structs.PresetStruct(
        presetHandle=b"\xff",
        presetScenario=255,  # Unmapped scenario
        name="",  # Empty name
    )
    presets_attribute.append(new_preset)

    # Update the node with the new preset list
    set_node_attribute(
        matter_node,
        1,
        513,
        clusters.Thermostat.Attributes.Presets.attribute_id,
        presets_attribute,
    )

    # Trigger subscription callback to update entity
    await trigger_subscription_callback(hass, matter_client)

    # Verify the preset was added with the fallback name "Preset8"
    state = hass.states.get(entity_id)
    assert state
    assert "Preset8" in state.attributes["preset_modes"]

    # Test that the unnamed preset can be set as active
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "Preset8",
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "Preset8"

    # Test that preset_mode is PRESET_NONE when ActivePresetHandle is cleared
    set_node_attribute(
        matter_node,
        1,
        513,
        clusters.Thermostat.Attributes.ActivePresetHandle.attribute_id,
        None,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == PRESET_NONE


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
@pytest.mark.parametrize("attributes", [{"1/513/0": None}])
async def test_thermostat_with_null_local_temperature(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat is created when LocalTemperature is null."""
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["current_temperature"] is None


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
@pytest.mark.parametrize(
    ("system_mode", "hvac_mode"),
    [
        pytest.param(1, HVACMode.HEAT_COOL, id="auto"),
        pytest.param(3, HVACMode.COOL, id="cool"),
        pytest.param(4, HVACMode.HEAT, id="heat"),
    ],
)
async def test_turn_on_restores_reported_mode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    system_mode: int,
    hvac_mode: HVACMode,
) -> None:
    """Only turn_on restores the mode reported before an external shutdown."""
    set_node_attribute(matter_node, 1, 513, 28, system_mode)
    await trigger_subscription_callback(hass, matter_client)
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )

    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=system_mode
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == hvac_mode


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
@pytest.mark.parametrize(
    "attributes", [{"1/513/28": 1}, {"1/513/28": 3}, {"1/513/28": 4}]
)
@pytest.mark.usefixtures("matter_node")
async def test_turn_on_keeps_running_mode(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Turning on an already running thermostat does not send commands."""
    initial_state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert initial_state
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()
    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == initial_state.state


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_turn_on_after_reload(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """Reload keeps the thermostat off until turn_on restores its previous mode."""
    await hass.services.async_call(
        "climate", "turn_off", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.reset_mock()

    entry = hass.config_entries.async_entries("matter")[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=3
    )


@pytest.mark.parametrize(
    ("stored_mode", "system_mode", "expected_mode"),
    [
        pytest.param("cool", 0, 3, id="restore-cool"),
        pytest.param("heat", 0, 4, id="restore-heat"),
        pytest.param("heat_cool", 0, 1, id="restore-auto"),
        pytest.param(None, 0, 1, id="no-history"),
        pytest.param("off", 0, 1, id="off-history"),
        pytest.param("invalid", 0, 1, id="invalid-history"),
        pytest.param("fan_only", 0, 1, id="unsupported-history"),
        pytest.param("heat", 3, 3, id="live-mode-takes-precedence"),
    ],
)
async def test_turn_on_restored_history(
    hass: HomeAssistant,
    matter_client: MagicMock,
    stored_mode: str | None,
    system_mode: int,
    expected_mode: int,
) -> None:
    """Stored history never overrides device state or sends commands on setup."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State(THERMOSTAT_ENTITY_ID, HVACMode.OFF), {"last_hvac_mode": stored_mode})],
    )
    matter_node = await setup_integration_with_node_fixture(
        hass, "longan_link_thermostat", matter_client, {"1/513/28": system_mode}
    )
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()

    # An external shutdown must not overwrite the last running mode.
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.assert_not_called()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=expected_mode
    )


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_turn_on_after_supported_modes_change(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """Fall back when a previously used mode is no longer supported."""
    set_node_attribute(matter_node, 1, 513, 28, 0)
    set_node_attribute(
        matter_node, 1, 513, 65532, clusters.Thermostat.Bitmaps.Feature.kHeating
    )
    await trigger_subscription_callback(hass, matter_client)
    matter_client.write_attribute.assert_not_called()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=4
    )


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize("attributes", [{"1/6/0": True, "1/513/28": 4}])
@pytest.mark.parametrize(
    ("hvac_mode", "system_mode"),
    [
        pytest.param(HVACMode.COOL, 3, id="cool"),
        pytest.param(HVACMode.HEAT_COOL, 1, id="auto"),
        pytest.param(HVACMode.DRY, 8, id="dry"),
        pytest.param(HVACMode.FAN_ONLY, 7, id="fan-only"),
    ],
)
async def test_turn_on_uses_mode_selected_with_power_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hvac_mode: HVACMode,
    system_mode: int,
) -> None:
    """Powering on resumes the mode explicitly selected while power was off."""
    set_node_attribute(matter_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)
    matter_client.write_attribute.assert_not_called()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": ROOM_AC_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=system_mode
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(ROOM_AC_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.send_device_command.assert_not_called()
    matter_client.write_attribute.reset_mock()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_called_once_with(
        node_id=matter_node.node_id, endpoint_id=1, command=clusters.OnOff.Commands.On()
    )


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize("attributes", [{"1/6/0": True, "1/513/28": 4}])
async def test_failed_mode_write_keeps_previous_mode(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """A failed mode write while power is off does not change the remembered mode."""
    set_node_attribute(matter_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)
    matter_client.write_attribute.side_effect = MatterError("Mode write failed")
    with pytest.raises(HomeAssistantError, match="Mode write failed"):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": ROOM_AC_ENTITY_ID, "hvac_mode": HVACMode.COOL},
            blocking=True,
        )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=3
    )
    matter_client.send_device_command.assert_not_called()
    matter_client.write_attribute.side_effect = None
    # Clear the selected mode so turn_on must use history rather than the live mode.
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    matter_client.reset_mock()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    assert matter_client.method_calls == [
        call.send_device_command(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.OnOff.Commands.On(),
        ),
        call.write_attribute(
            node_id=matter_node.node_id, attribute_path="1/513/28", value=4
        ),
    ]


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize(
    "attributes",
    [
        pytest.param({"1/6/0": True, "1/513/28": 3}, id="cool-before-power-off"),
        pytest.param({"1/6/0": True, "1/513/28": 4}, id="cool-selected-while-off"),
    ],
)
async def test_mode_reported_while_powered_off_is_remembered(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """Remember external mode changes even when dedicated power is off."""
    set_node_attribute(matter_node, 1, 6, 0, False)
    set_node_attribute(matter_node, 1, 513, 28, 3)
    await trigger_subscription_callback(hass, matter_client)
    # Clear SystemMode to exercise the remembered mode on the next turn_on.
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(ROOM_AC_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()
    matter_client.reset_mock()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    assert matter_client.method_calls == [
        call.send_device_command(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.OnOff.Commands.On(),
        ),
        call.write_attribute(
            node_id=matter_node.node_id, attribute_path="1/513/28", value=3
        ),
    ]


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize(
    "attributes",
    [{"1/6/0": True, "1/513/28": 3, "1/513/65532": 3, "0/40/2": 0, "0/40/4": 0}],
)
async def test_unsupported_reported_mode_keeps_remembered_mode(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """A reported mode the entity does not support does not replace history."""
    set_node_attribute(matter_node, 1, 513, 28, 8)
    await trigger_subscription_callback(hass, matter_client)
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    matter_client.reset_mock()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=3
    )


@pytest.mark.parametrize(
    "stored_mode",
    [pytest.param(None, id="no-history"), pytest.param("heat", id="stale-history")],
)
async def test_powered_off_startup_remembers_device_mode(
    hass: HomeAssistant, matter_client: MagicMock, stored_mode: str | None
) -> None:
    """The device's selected mode at startup takes precedence over saved history."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State(ROOM_AC_ENTITY_ID, HVACMode.OFF), {"last_hvac_mode": stored_mode})],
    )
    matter_node = await setup_integration_with_node_fixture(
        hass, "mock_room_airconditioner", matter_client, {"1/6/0": False, "1/513/28": 3}
    )
    state = hass.states.get(ROOM_AC_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    matter_client.reset_mock()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    assert matter_client.method_calls == [
        call.send_device_command(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.OnOff.Commands.On(),
        ),
        call.write_attribute(
            node_id=matter_node.node_id, attribute_path="1/513/28", value=3
        ),
    ]


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize(
    ("attributes", "expected_mode"),
    [
        pytest.param({"1/6/0": False, "1/513/28": 0}, 1, id="no-mode"),
        pytest.param(
            {"1/6/0": False, "1/513/28": 8, "1/513/65532": 1, "0/40/2": 0, "0/40/4": 0},
            4,
            id="unsupported-mode",
        ),
    ],
)
async def test_dead_front_powers_on_before_mode_write(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    expected_mode: int,
) -> None:
    """Mode writes are only attempted after the device accepts On."""

    async def write_after_power_on(**kwargs: object) -> None:
        """Reject a mode write while the device is in dead front."""
        matter_client.send_device_command.assert_awaited_once_with(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.OnOff.Commands.On(),
        )

    matter_client.reset_mock()
    matter_client.write_attribute.side_effect = write_after_power_on
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    assert matter_client.method_calls == [
        call.send_device_command(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.OnOff.Commands.On(),
        ),
        call.write_attribute(
            node_id=matter_node.node_id, attribute_path="1/513/28", value=expected_mode
        ),
    ]


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize("attributes", [{"1/6/0": False, "1/513/28": 3}])
async def test_turn_on_keeps_retained_mode_without_writing(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """A device retaining its own mode needs only the On command."""
    matter_client.write_attribute.side_effect = MatterError("INVALID_IN_STATE")
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_awaited_once_with(
        node_id=matter_node.node_id, endpoint_id=1, command=clusters.OnOff.Commands.On()
    )


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize("attributes", [{"1/6/0": False, "1/513/28": 0}])
@pytest.mark.usefixtures("matter_node")
async def test_failed_power_on_does_not_write_mode(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Do not write a mode if powering on failed."""
    matter_client.send_device_command.side_effect = MatterError("Power on failed")
    with pytest.raises(HomeAssistantError, match="Power on failed"):
        await hass.services.async_call(
            "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
        )
    matter_client.write_attribute.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_set_thermostat_preset_edit(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Editing a preset reads the live list and writes it with the cluster's data version."""
    _mock_preset_write(matter_client)

    await hass.services.async_call(
        DOMAIN,
        "set_thermostat_preset",
        {
            TargetKey.ENTITY_ID: EVE_THERMO_ENTITY_ID,
            ATTR_PRESET_MODE: "home",
            ATTR_HEATING_SETPOINT: 23.5,
        },
        blocking=True,
    )

    matter_client.read.assert_awaited_once_with(
        matter_node.node_id, [PRESETS_ATTRIBUTE_PATH]
    )
    written = matter_client.write_atomic_attribute.call_args
    assert written.kwargs["node_id"] == matter_node.node_id
    assert written.kwargs["attribute_path"] == PRESETS_ATTRIBUTE_PATH
    assert written.kwargs["data_version"] == 1
    new_presets = written.kwargs["value"]
    assert len(new_presets) == 7
    edited = next(p for p in new_presets if p.presetHandle == b"\x01")
    assert edited.heatingSetpoint == 2350
    assert edited.name == "Home"
    assert edited.builtIn is True
    # untouched presets keep their original values
    sleep = next(p for p in new_presets if p.presetHandle == b"\x03")
    assert sleep.heatingSetpoint == 2000


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize("attributes", [{"1/513/72": TWO_OCCUPIED_PRESET_TYPES}])
async def test_set_thermostat_preset_add(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Adding a preset appends a new entry with a null handle."""
    _mock_preset_write(matter_client)

    await hass.services.async_call(
        DOMAIN,
        "set_thermostat_preset",
        {
            ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
            ATTR_PRESET_SCENARIO: "occupied",
            ATTR_PRESET_NAME: "Home 2",
            ATTR_HEATING_SETPOINT: 21.0,
        },
        blocking=True,
    )

    new_presets = matter_client.write_atomic_attribute.call_args.kwargs["value"]
    assert len(new_presets) == 8
    added = new_presets[-1]
    assert added.presetHandle is NullValue
    assert added.presetScenario == 1
    assert added.name == "Home 2"
    assert added.heatingSetpoint == 2100
    assert added.builtIn is False


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize("attributes", [{"1/513/72": TWO_OCCUPIED_PRESET_TYPES}])
async def test_set_thermostat_preset_add_duplicate_name(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Adding a preset with a duplicate name in the same scenario is refused."""
    _mock_preset_write(matter_client)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_SCENARIO: "occupied",
                ATTR_PRESET_NAME: "Home",
                ATTR_HEATING_SETPOINT: 21.0,
            },
            blocking=True,
        )

    assert err.value.translation_key == "preset_name_not_unique"
    matter_client.write_atomic_attribute.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize("attributes", [{"1/513/72": TWO_OCCUPIED_PRESET_TYPES}])
async def test_set_thermostat_preset_edit_duplicate_name(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Editing a preset with a duplicate name in the same scenario is refused."""
    current_presets = [
        *_eve_thermo_presets(),
        clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\x07",
            presetScenario=1,
            name="Home 2",
            coolingSetpoint=None,
            heatingSetpoint=2100,
            builtIn=False,
        ),
    ]
    _mock_preset_write(matter_client, current_presets)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_MODE: "home",
                ATTR_PRESET_NAME: "Home 2",
                ATTR_HEATING_SETPOINT: 23.5,
            },
            blocking=True,
        )

    assert err.value.translation_key == "preset_name_not_unique"
    matter_client.write_atomic_attribute.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_clear_thermostat_preset(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Removing a preset writes the list without it."""
    _mock_preset_write(matter_client)

    await hass.services.async_call(
        DOMAIN,
        "clear_thermostat_preset",
        {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: "sleep"},
        blocking=True,
    )

    new_presets = matter_client.write_atomic_attribute.call_args.kwargs["value"]
    assert len(new_presets) == 6
    assert all(p.presetHandle != b"\x03" for p in new_presets)


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_clear_thermostat_preset_active_blocked(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """The active preset is refused before anything is written."""
    # make "sleep" (handle 0x03) the active preset instead of the built-in "home"
    set_node_attribute(matter_node, 1, 513, 78, b"\x03")
    _mock_preset_write(matter_client)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "clear_thermostat_preset",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: "sleep"},
            blocking=True,
        )
    assert err.value.translation_key == "preset_active_not_removable"
    matter_client.write_atomic_attribute.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_clear_thermostat_preset_builtin_blocked(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A built-in preset is refused before anything is written."""
    _mock_preset_write(matter_client)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "clear_thermostat_preset",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: "home"},
            blocking=True,
        )
    assert err.value.translation_key == "preset_builtin_not_removable"
    matter_client.write_atomic_attribute.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    ("preset_mode", "translation_key"),
    [
        ("does_not_exist", "preset_unknown"),
        (PRESET_NONE, "preset_not_removable"),
    ],
)
async def test_clear_thermostat_preset_invalid_preset_mode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    preset_mode: str,
    translation_key: str,
) -> None:
    """Unknown and non-removable preset modes raise a validation error."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "clear_thermostat_preset",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
            blocking=True,
        )
    assert err.value.translation_key == translation_key


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_clear_thermostat_preset_matter_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A low-level MatterError while reading the live list is wrapped."""
    matter_client.read = AsyncMock(side_effect=MatterError("Unreachable"))

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "clear_thermostat_preset",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: "sleep"},
            blocking=True,
        )
    assert err.value.translation_key == "preset_update_failed"


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    ("preset_mode", "translation_key"),
    [
        ("does_not_exist", "preset_unknown"),
        (PRESET_NONE, "preset_not_editable"),
    ],
)
async def test_set_thermostat_preset_invalid_preset_mode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    preset_mode: str,
    translation_key: str,
) -> None:
    """Unknown and non-editable preset modes raise a validation error."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_MODE: preset_mode,
                ATTR_HEATING_SETPOINT: 20.0,
            },
            blocking=True,
        )
    assert err.value.translation_key == translation_key


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_set_thermostat_preset_requires_scenario_when_adding(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Adding a preset without a scenario raises a validation error."""
    _mock_preset_write(matter_client)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_NAME: "New preset"},
            blocking=True,
        )
    assert err.value.translation_key == "preset_scenario_required"
    matter_client.read.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_set_thermostat_preset_scenario_not_editable(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """preset_scenario cannot be combined with an existing preset_mode."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_MODE: "home",
                ATTR_PRESET_SCENARIO: "sleep",
            },
            blocking=True,
        )
    assert err.value.translation_key == "preset_scenario_not_editable"


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    ("service_data", "translation_key"),
    [
        (
            {ATTR_PRESET_SCENARIO: "user_defined", ATTR_HEATING_SETPOINT: 20.0},
            "preset_name_required",
        ),
        (
            {ATTR_PRESET_SCENARIO: "occupied", ATTR_PRESET_NAME: "Home 2"},
            "preset_heating_setpoint_required",
        ),
    ],
)
async def test_set_thermostat_preset_add_missing_data(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    service_data: dict[str, Any],
    translation_key: str,
) -> None:
    """A new preset without the data its scenario requires is refused before reading."""
    _mock_preset_write(matter_client)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, **service_data},
            blocking=True,
        )
    assert err.value.translation_key == translation_key
    matter_client.read.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    ("status", "translation_key"),
    [
        (
            clusters.Globals.Enums.status.kBusy,
            "preset_write_busy",
        ),
        (
            clusters.Globals.Enums.status.kInvalidInState,
            "preset_write_invalid_in_state",
        ),
        (
            clusters.Globals.Enums.status.kConstraintError,
            "preset_write_failed",
        ),
    ],
)
async def test_set_thermostat_preset_rejected_by_device(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    status: int,
    translation_key: str,
) -> None:
    """The device's own write-rule validation rejects the write."""
    _mock_preset_write(matter_client)
    matter_client.write_atomic_attribute.return_value = [{"Status": status}]

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_MODE: "home",
                ATTR_HEATING_SETPOINT: 20.0,
            },
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    assert matter_client.read.await_count == 1


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_set_thermostat_preset_retries_on_data_version_mismatch(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A DATA_VERSION_MISMATCH rereads the list and retries the write once."""
    _mock_preset_write(matter_client)
    matter_client.write_atomic_attribute.side_effect = [
        [{"Status": clusters.Globals.Enums.status.kDataVersionMismatch}],
        [{"Status": clusters.Globals.Enums.status.kSuccess}],
    ]

    await hass.services.async_call(
        DOMAIN,
        "set_thermostat_preset",
        {
            ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
            ATTR_PRESET_MODE: "home",
            ATTR_HEATING_SETPOINT: 20.0,
        },
        blocking=True,
    )

    assert matter_client.read.await_count == 2
    assert matter_client.write_atomic_attribute.await_count == 2


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_set_thermostat_preset_matter_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A low-level MatterError while reading the live list is wrapped."""
    matter_client.read = AsyncMock(side_effect=MatterError("Unreachable"))

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_MODE: "home",
                ATTR_HEATING_SETPOINT: 20.0,
            },
            blocking=True,
        )
    assert err.value.translation_key == "preset_update_failed"


def _preset(
    handle: bytes,
    scenario: int,
    name: str | None,
    built_in: bool | None = False,
) -> clusters.Thermostat.Structs.PresetStruct:
    """Return a heating preset."""
    return clusters.Thermostat.Structs.PresetStruct(
        presetHandle=handle,
        presetScenario=scenario,
        name=name,
        coolingSetpoint=None,
        heatingSetpoint=2100,
        builtIn=NullValue if built_in is None else built_in,
    )


async def _set_presets(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    presets: list[clusters.Thermostat.Structs.PresetStruct],
) -> None:
    """Report a new Presets list for the eve thermostat."""
    set_node_attribute(
        matter_node,
        1,
        THERMOSTAT_CLUSTER_ID,
        PRESETS_ATTRIBUTE_ID,
        presets,
    )
    await trigger_subscription_callback(hass, matter_client)


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    "added_first",
    [pytest.param(True, id="added_first"), pytest.param(False, id="added_last")],
)
async def test_added_preset_does_not_shadow_builtin_name(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    added_first: bool,
) -> None:
    """A second preset of a scenario keeps its own name wherever the device lists it."""
    added = _preset(b"\x07", 1, "Guests")
    presets = _eve_thermo_presets()
    await _set_presets(
        hass,
        matter_client,
        matter_node,
        [added, *presets] if added_first else [*presets, added],
    )

    state = hass.states.get(EVE_THERMO_ENTITY_ID)
    assert state
    assert "home (Guests)" in state.attributes["preset_modes"]

    for preset_mode, handle in (("home", b"\x01"), ("home (Guests)", b"\x07")):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
            blocking=True,
        )
        assert matter_client.send_device_command.call_args == call(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.Thermostat.Commands.SetActivePresetRequest(
                presetHandle=handle
            ),
        )


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_preset_names_survive_removal(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Unnamed presets of one scenario are named by handle, so a suffixed name stays with its preset."""
    presets = [_preset(b"\x10", 3, None), _preset(b"\x11", 3, None)]
    await _set_presets(
        hass, matter_client, matter_node, [*presets, _preset(b"\x12", 3, None)]
    )
    state = hass.states.get(EVE_THERMO_ENTITY_ID)
    assert state
    assert state.attributes["preset_modes"] == [
        "sleep",
        "sleep (11)",
        "sleep (12)",
        PRESET_NONE,
    ]

    await _set_presets(
        hass, matter_client, matter_node, [presets[1], _preset(b"\x12", 3, None)]
    )
    state = hass.states.get(EVE_THERMO_ENTITY_ID)
    assert state
    assert state.attributes["preset_modes"] == ["sleep", "sleep (12)", PRESET_NONE]


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_user_defined_preset_named_like_scenario(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A user-defined preset named like a scenario or `none` gets its handle appended."""
    await _set_presets(
        hass,
        matter_client,
        matter_node,
        [
            _preset(b"\x20", 254, "home"),
            _preset(b"\x21", 254, PRESET_NONE),
            _preset(b"\x01", 1, "Home", built_in=True),
        ],
    )
    state = hass.states.get(EVE_THERMO_ENTITY_ID)
    assert state
    assert state.attributes["preset_modes"] == [
        "home (20)",
        "none (21)",
        "home",
        PRESET_NONE,
    ]


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize("attributes", [_thermostat_on_endpoint_2()])
async def test_set_thermostat_preset_targets_entity_endpoint(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A preset written from a second thermostat entity uses that thermostat's endpoint."""
    _mock_preset_write(matter_client, endpoint_id=2)

    await hass.services.async_call(
        DOMAIN,
        "set_thermostat_preset",
        {
            ATTR_ENTITY_ID: "climate.eve_thermo_20ecd1701_thermostat_2",
            ATTR_PRESET_SCENARIO: "occupied",
            ATTR_PRESET_NAME: "Home 2",
            ATTR_HEATING_SETPOINT: 21.0,
        },
        blocking=True,
    )

    matter_client.read.assert_awaited_once_with(matter_node.node_id, ["2/513/80"])
    written = matter_client.write_atomic_attribute.call_args
    assert written.kwargs["attribute_path"] == "2/513/80"
    assert written.kwargs["data_version"] == 1


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        pytest.param(
            ServerVersionTooOld("schema 11"), "preset_server_too_old", id="too_old"
        ),
        pytest.param(
            InvalidState("Not connected"), "preset_update_failed", id="disconnected"
        ),
    ],
)
@pytest.mark.parametrize(
    "service_call",
    [
        pytest.param(
            (
                "set_thermostat_preset",
                {ATTR_PRESET_MODE: "home", ATTR_HEATING_SETPOINT: 20.0},
            ),
            id="set",
        ),
        pytest.param(
            ("clear_thermostat_preset", {ATTR_PRESET_MODE: "sleep"}), id="clear"
        ),
    ],
)
async def test_thermostat_preset_client_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    side_effect: Exception,
    translation_key: str,
    service_call: tuple[str, dict[str, Any]],
) -> None:
    """Client exceptions, such as a server too old for atomic writes, are translated."""
    matter_client.read = AsyncMock(side_effect=side_effect)
    service_name, service_data = service_call

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, **service_data},
            blocking=True,
        )
    assert err.value.translation_key == translation_key


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_set_thermostat_preset_data_version_mismatch_exhausted(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A second DATA_VERSION_MISMATCH is reported instead of retried again."""
    _mock_preset_write(matter_client)
    matter_client.write_atomic_attribute.return_value = [
        {"Status": clusters.Globals.Enums.status.kDataVersionMismatch}
    ]

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_MODE: "home",
                ATTR_HEATING_SETPOINT: 20.0,
            },
            blocking=True,
        )
    assert err.value.translation_key == "preset_write_data_version_mismatch"
    assert matter_client.read.await_count == 2
    assert matter_client.write_atomic_attribute.await_count == 2


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    ("attributes", "service_data", "translation_key"),
    [
        pytest.param(
            {"1/513/72": [pt for pt in TWO_OCCUPIED_PRESET_TYPES if pt["0"] != 254]},
            {
                ATTR_PRESET_SCENARIO: "user_defined",
                ATTR_PRESET_NAME: "Guests",
                ATTR_HEATING_SETPOINT: 20.0,
            },
            "preset_scenario_not_supported",
            id="scenario_not_supported",
        ),
        pytest.param(
            {"1/513/72": TWO_OCCUPIED_PRESET_TYPES, "1/513/74": 7},
            {ATTR_PRESET_SCENARIO: "occupied", ATTR_HEATING_SETPOINT: 20.0},
            "preset_limit_reached",
            id="total_limit",
        ),
        pytest.param(
            {},
            {ATTR_PRESET_SCENARIO: "occupied", ATTR_HEATING_SETPOINT: 20.0},
            "preset_scenario_limit_reached",
            id="scenario_limit",
        ),
        pytest.param(
            {"1/513/72": TWO_OCCUPIED_PRESET_TYPES},
            {ATTR_PRESET_SCENARIO: "occupied", ATTR_HEATING_SETPOINT: 35.0},
            "preset_heating_setpoint_out_of_range",
            id="heating_out_of_range",
        ),
        pytest.param(
            {"1/513/72": TWO_OCCUPIED_PRESET_TYPES, "1/513/65532": 259},
            {ATTR_PRESET_SCENARIO: "occupied", ATTR_HEATING_SETPOINT: 20.0},
            "preset_cooling_setpoint_required",
            id="cooling_required",
        ),
        pytest.param(
            {
                "1/513/72": TWO_OCCUPIED_PRESET_TYPES,
                "1/513/65532": 259,
                "1/513/5": 1600,
                "1/513/6": 3200,
            },
            {
                ATTR_PRESET_SCENARIO: "occupied",
                ATTR_HEATING_SETPOINT: 20.0,
                ATTR_COOLING_SETPOINT: 15.0,
            },
            "preset_cooling_setpoint_out_of_range",
            id="cooling_out_of_range",
        ),
    ],
)
async def test_set_thermostat_preset_add_refused_by_limits(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    service_data: dict[str, Any],
    translation_key: str,
) -> None:
    """A new preset the device's limits rule out is refused before reading."""
    _mock_preset_write(matter_client)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, **service_data},
            blocking=True,
        )
    assert err.value.translation_key == translation_key
    matter_client.read.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_set_thermostat_preset_edit_setpoint_out_of_range(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """An edit with a setpoint outside the thermostat's limits is refused before reading."""
    _mock_preset_write(matter_client)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_MODE: "home",
                ATTR_HEATING_SETPOINT: 5.0,
            },
            blocking=True,
        )
    assert err.value.translation_key == "preset_heating_setpoint_out_of_range"
    assert err.value.translation_placeholders == {"min": "10.0", "max": "30.0"}
    matter_client.read.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    ("service_name", "service_data"),
    [
        pytest.param(
            "set_thermostat_preset",
            {ATTR_PRESET_MODE: "sleep", ATTR_HEATING_SETPOINT: 20.0},
            id="set",
        ),
        pytest.param(
            "clear_thermostat_preset", {ATTR_PRESET_MODE: "sleep"}, id="clear"
        ),
    ],
)
async def test_thermostat_preset_removed_on_device(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    service_name: str,
    service_data: dict[str, Any],
) -> None:
    """A preset that is gone from the live list is reported instead of written."""
    _mock_preset_write(
        matter_client,
        [p for p in _eve_thermo_presets() if p.presetHandle != b"\x03"],
    )
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, **service_data},
            blocking=True,
        )
    assert err.value.translation_key == "preset_not_found_on_device"
    matter_client.write_atomic_attribute.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize(
    "read_attributes",
    [
        pytest.param({}, id="missing"),
        pytest.param({PRESETS_ATTRIBUTE_PATH: None}, id="null"),
    ],
)
async def test_clear_thermostat_preset_not_reported(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    read_attributes: dict[str, Any],
) -> None:
    """A read without a Presets list is reported instead of written."""
    matter_client.read = AsyncMock(
        return_value=InteractionReport(
            attributes=read_attributes,
            events=[],
            data_versions={THERMOSTAT_CLUSTER_PATH: 1},
        )
    )
    matter_client.write_atomic_attribute = AsyncMock()
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "clear_thermostat_preset",
            {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: "sleep"},
            blocking=True,
        )
    assert err.value.translation_key == "presets_not_reported"
    matter_client.write_atomic_attribute.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
@pytest.mark.parametrize("attributes", [{"1/513/65532": 1}])
async def test_set_thermostat_preset_not_supported(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A thermostat without the Presets feature refuses a new preset."""
    _mock_preset_write(matter_client)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_thermostat_preset",
            {
                ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID,
                ATTR_PRESET_SCENARIO: "occupied",
                ATTR_HEATING_SETPOINT: 20.0,
            },
            blocking=True,
        )
    assert err.value.translation_key == "presets_not_supported"
    matter_client.read.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_clear_thermostat_preset_null_builtin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A preset reporting a null BuiltIn is not treated as built-in."""
    presets = _eve_thermo_presets()
    presets[2] = _preset(b"\x03", 3, "Sleep", built_in=None)
    await _set_presets(hass, matter_client, matter_node, presets)
    _mock_preset_write(matter_client)

    await hass.services.async_call(
        DOMAIN,
        "clear_thermostat_preset",
        {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: "sleep"},
        blocking=True,
    )
    new_presets = matter_client.write_atomic_attribute.call_args.kwargs["value"]
    assert all(p.presetHandle != b"\x03" for p in new_presets)


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_empty_presets_during_write_keep_preset_mode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """An empty Presets report during an atomic write keeps the preset mode."""
    _mock_preset_write(matter_client)

    # Conserver le résultat avant d'installer le side_effect.
    write_result = matter_client.write_atomic_attribute.return_value

    async def write_with_empty_report(*args: Any, **kwargs: Any) -> Any:
        await _set_presets(hass, matter_client, matter_node, [])

        state = hass.states.get(EVE_THERMO_ENTITY_ID)
        assert state
        assert state.attributes["preset_mode"] == "home"
        assert "sleep" in state.attributes["preset_modes"]

        return write_result

    matter_client.write_atomic_attribute.side_effect = write_with_empty_report

    await hass.services.async_call(
        DOMAIN,
        "clear_thermostat_preset",
        {ATTR_ENTITY_ID: EVE_THERMO_ENTITY_ID, ATTR_PRESET_MODE: "sleep"},
        blocking=True,
    )
