"""Test Matter Fan platform."""

from unittest.mock import MagicMock, call

from matter_server.client.models.node import MatterNode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    FanEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_fans(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fans."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.FAN)


@pytest.mark.parametrize("node_fixture", ["air_purifier"])
async def test_fan_base(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Fan platform."""
    entity_id = "fan.air_purifier"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_modes"] == [
        "low",
        "medium",
        "high",
        "auto",
        "natural_wind",
        "sleep_wind",
    ]
    assert state.attributes["direction"] == "forward"
    assert state.attributes["oscillating"] is False
    assert state.attributes["percentage"] is None
    assert state.attributes["percentage_step"] == 10
    assert state.attributes["preset_mode"] == "auto"
    mask = (
        FanEntityFeature.DIRECTION
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
    )
    assert state.attributes["supported_features"] & mask == mask
    # handle fan mode update
    set_node_attribute(matter_node, 1, 514, 0, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.attributes["preset_mode"] == "low"
    # handle direction update
    set_node_attribute(matter_node, 1, 514, 11, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.attributes["direction"] == "reverse"
    # handle rock/oscillation update
    set_node_attribute(matter_node, 1, 514, 8, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.attributes["oscillating"] is True
    # handle wind mode active translates to correct preset
    set_node_attribute(matter_node, 1, 514, 10, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.attributes["preset_mode"] == "natural_wind"
    set_node_attribute(matter_node, 1, 514, 10, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.attributes["preset_mode"] == "sleep_wind"
    # set mains power to OFF (OnOff cluster)
    set_node_attribute(matter_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.attributes["preset_mode"] is None
    assert state.attributes["percentage"] == 0
    # test featuremap update
    set_node_attribute(matter_node, 1, 514, 65532, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.attributes["supported_features"] & FanEntityFeature.SET_SPEED


@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize("node_fixture", ["air_purifier"])
async def test_fan_turn_on_with_percentage(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test turning on the fan with a specific percentage."""
    entity_id = "fan.air_purifier"
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/2",
        value=50,
    )
    # test again where preset_mode is omitted in the service call
    # which should select the last active percentage
    matter_client.write_attribute.reset_mock()
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/2",
        value=255,
    )


@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize("node_fixture", ["fan"])
async def test_fan_turn_on_with_preset_mode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test turning on the fan with a specific preset mode."""
    entity_id = "fan.mocked_fan_switch"
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: "medium"},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/0",
        value=2,
    )
    # test again with wind feature as preset mode
    for preset_mode, value in (("natural_wind", 2), ("sleep_wind", 1)):
        matter_client.write_attribute.reset_mock()
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset_mode},
            blocking=True,
        )
        assert matter_client.write_attribute.call_count == 1
        assert matter_client.write_attribute.call_args == call(
            node_id=matter_node.node_id,
            attribute_path="1/514/10",
            value=value,
        )
    # test again if wind mode is explicitly turned off when we set a new preset mode
    matter_client.write_attribute.reset_mock()
    set_node_attribute(matter_node, 1, 514, 10, 2)
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: "medium"},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/10",
        value=0,
    )
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/0",
        value=2,
    )
    # test again where preset_mode is omitted in the service call
    # which should select the last active preset
    matter_client.write_attribute.reset_mock()
    set_node_attribute(matter_node, 1, 514, 0, 1)
    set_node_attribute(matter_node, 1, 514, 10, 0)
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/0",
        value=1,
    )


@pytest.mark.parametrize("node_fixture", ["air_purifier"])
async def test_fan_turn_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test turning off the fan."""
    entity_id = "fan.air_purifier"
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/0",
        value=0,
    )
    matter_client.write_attribute.reset_mock()
    # test again if wind mode is turned off
    set_node_attribute(matter_node, 1, 514, 10, 2)
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/10",
        value=0,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/514/0",
        value=0,
    )


@pytest.mark.parametrize("node_fixture", ["air_purifier"])
async def test_fan_oscillate(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test oscillating the fan."""
    entity_id = "fan.air_purifier"
    for oscillating, value in ((True, 1), (False, 0)):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_OSCILLATE,
            {ATTR_ENTITY_ID: entity_id, ATTR_OSCILLATING: oscillating},
            blocking=True,
        )
        assert matter_client.write_attribute.call_count == 1
        assert matter_client.write_attribute.call_args == call(
            node_id=matter_node.node_id,
            attribute_path="1/514/8",
            value=value,
        )
        matter_client.write_attribute.reset_mock()


@pytest.mark.parametrize("node_fixture", ["air_purifier"])
async def test_fan_set_direction(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test oscillating the fan."""
    entity_id = "fan.air_purifier"
    for direction, value in ((DIRECTION_FORWARD, 0), (DIRECTION_REVERSE, 1)):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_DIRECTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_DIRECTION: direction},
            blocking=True,
        )
        assert matter_client.write_attribute.call_count == 1
        assert matter_client.write_attribute.call_args == call(
            node_id=matter_node.node_id,
            attribute_path="1/514/11",
            value=value,
        )
        matter_client.write_attribute.reset_mock()


@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "attributes", "features"),
    [
        (
            "fan",
            "fan.mocked_fan_switch",
            {
                "1/514/65532": 0,
            },
            (FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF),
        ),
        (
            "fan",
            "fan.mocked_fan_switch",
            {
                "1/514/65532": 1,
            },
            (
                FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.SET_SPEED
            ),
        ),
        (
            "fan",
            "fan.mocked_fan_switch",
            {
                "1/514/65532": 4,
            },
            (
                FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.OSCILLATE
            ),
        ),
        (
            "fan",
            "fan.mocked_fan_switch",
            {
                "1/514/65532": 36,
            },
            (
                FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.OSCILLATE
                | FanEntityFeature.DIRECTION
            ),
        ),
    ],
)
async def test_fan_supported_features(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    features: int,
) -> None:
    """Test if the correct features get discovered from featuremap."""
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] & features == features


@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "attributes", "preset_modes"),
    [
        (
            "fan",
            "fan.mocked_fan_switch",
            {"1/514/1": 0, "1/514/65532": 0},
            [
                "low",
                "medium",
                "high",
            ],
        ),
        (
            "fan",
            "fan.mocked_fan_switch",
            {"1/514/1": 1, "1/514/65532": 0},
            [
                "low",
                "high",
            ],
        ),
        (
            "fan",
            "fan.mocked_fan_switch",
            {"1/514/1": 2, "1/514/65532": 0},
            ["low", "medium", "high", "auto"],
        ),
        (
            "fan",
            "fan.mocked_fan_switch",
            {"1/514/1": 4, "1/514/65532": 0},
            ["high", "auto"],
        ),
        (
            "fan",
            "fan.mocked_fan_switch",
            {"1/514/1": 5, "1/514/65532": 0},
            ["high"],
        ),
        (
            "fan",
            "fan.mocked_fan_switch",
            {"1/514/1": 5, "1/514/65532": 8, "1/514/9": 3},
            ["high", "natural_wind", "sleep_wind"],
        ),
    ],
)
async def test_fan_features(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    preset_modes: list[str],
) -> None:
    """Test if the correct presets get discovered from fanmodesequence."""
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_modes"] == preset_modes
