"""Test KNX fan."""

from typing import Any

import pytest

from homeassistant.components.knx.const import DOMAIN, KNX_ADDRESS, FanConf
from homeassistant.components.knx.schema import FanSchema
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import KnxEntityGenerator
from .conftest import KNXTestKit


async def test_fan_percent(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """Test KNX fan with percentage speed."""
    await knx.setup_integration(
        {
            FanSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
            }
        }
    )
    entry = entity_registry.async_get("fan.test")
    assert entry
    assert entry.unique_id == "1/2/3"

    # turn on fan with default speed (50%)
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (128,))

    # turn off fan
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (0,))

    # receive 100% telegram
    await knx.receive_write("1/2/3", (0xFF,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON

    # receive 80% telegram
    await knx.receive_write("1/2/3", (0xCC,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get("percentage") == 80

    # receive 0% telegram
    await knx.receive_write("1/2/3", (0,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF

    # fan does not respond to read
    await knx.receive_read("1/2/3")
    await knx.assert_telegram_count(0)


async def test_fan_step(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX fan with speed steps."""
    await knx.setup_integration(
        {
            FanSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                FanConf.MAX_STEP: 4,
            }
        }
    )

    # turn on fan with default speed (50% - step 2)
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (2,))

    # turn up speed to 75% - step 3
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test", "percentage": 75}, blocking=True
    )
    await knx.assert_write("1/2/3", (3,))

    # turn off fan
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (0,))

    # receive step 4 (100%) telegram
    await knx.receive_write("1/2/3", (4,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get("percentage") == 100

    # receive step 1 (25%) telegram
    await knx.receive_write("1/2/3", (1,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get("percentage") == 25

    # receive step 0 (off) telegram
    await knx.receive_write("1/2/3", (0,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF

    # fan does not respond to read
    await knx.receive_read("1/2/3")
    await knx.assert_telegram_count(0)


async def test_fan_switch(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """Test KNX fan with switch only."""
    await knx.setup_integration(
        {
            FanSchema.PLATFORM: {
                CONF_NAME: "test",
                FanSchema.CONF_SWITCH_ADDRESS: "1/2/3",
            }
        }
    )
    entry = entity_registry.async_get("fan.test")
    assert entry
    assert entry.unique_id == "1/2/3"

    # turn on fan
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", True)

    # turn off fan
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", False)


async def test_fan_switch_step(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """Test KNX fan with speed steps and switch address."""
    await knx.setup_integration(
        {
            FanSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/1/1",
                FanSchema.CONF_SWITCH_ADDRESS: "2/2/2",
                FanConf.MAX_STEP: 4,
            }
        }
    )
    entry = entity_registry.async_get("fan.test")
    assert entry
    assert entry.unique_id == "1/1/1"

    # turn on fan without percentage - actuator sets default speed
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("2/2/2", True)

    # turn on with speed 75% - step 3 - turn_on sends switch ON again
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test", "percentage": 75}, blocking=True
    )
    await knx.assert_write("2/2/2", True)
    await knx.assert_write("1/1/1", (3,))

    # set speed to 25% - step 1 - set_percentage doesn't send switch ON
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": "fan.test", "percentage": 25},
        blocking=True,
    )
    await knx.assert_write("1/1/1", (1,))

    # turn off fan - no percentage change sent
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("2/2/2", False)


async def test_fan_oscillation(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX fan oscillation."""
    await knx.setup_integration(
        {
            FanSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/1/1",
                FanSchema.CONF_OSCILLATION_ADDRESS: "2/2/2",
            }
        }
    )

    # turn on oscillation
    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": "fan.test", "oscillating": True},
        blocking=True,
    )
    await knx.assert_write("2/2/2", True)

    # turn off oscillation
    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": "fan.test", "oscillating": False},
        blocking=True,
    )
    await knx.assert_write("2/2/2", False)

    # receive oscillation on
    await knx.receive_write("2/2/2", True)
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is True

    # receive oscillation off
    await knx.receive_write("2/2/2", False)
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is False


@pytest.mark.parametrize(
    "fan_config",
    [
        {
            # before fix: unique_id is 'None', after fix: from switch address
            CONF_NAME: "test",
            FanSchema.CONF_SWITCH_ADDRESS: "1/2/3",
        },
        {
            # no change in unique_id here, but since no YAML to update from, the
            # invalid registry entry will be removed - it wouldn't be loaded anyway
            # this YAML will create a new entry (same unique_id as above for tests)
            CONF_NAME: "test",
            KNX_ADDRESS: "1/2/3",
        },
    ],
)
async def test_fan_unique_id_fix(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    fan_config: dict[str, Any],
) -> None:
    """Test KNX fan unique_id migration fix."""
    invalid_unique_id = "None"
    knx.mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        object_id_base="test",
        disabled_by=None,
        domain=Platform.FAN,
        platform=DOMAIN,
        unique_id=invalid_unique_id,
        config_entry=knx.mock_config_entry,
    )
    await knx.setup_integration(
        {FanSchema.PLATFORM: fan_config},
        add_entry_to_hass=False,
    )
    entry = entity_registry.async_get("fan.test")
    assert entry
    assert entry.unique_id == "1/2/3"
    # Verify the old entity with invalid unique_id has been updated or removed
    assert not entity_registry.async_get_entity_id(
        Platform.FAN, DOMAIN, invalid_unique_id
    )


@pytest.mark.parametrize(
    ("knx_data", "expected_read_response", "expected_state"),
    [
        (  # percent mode fan with oscillation
            {
                "speed": {
                    "ga_speed": {"write": "1/1/0", "state": "1/1/1"},
                },
                "ga_oscillation": {"write": "2/2/0", "state": "2/2/2"},
                "sync_state": True,
            },
            [("1/1/1", (0x55,)), ("2/2/2", True)],
            {"state": STATE_ON, "percentage": 33, "oscillating": True},
        ),
        (  # step only fan
            {
                "speed": {
                    "ga_step": {"write": "1/1/0", "state": "1/1/1"},
                    "max_step": 3,
                },
                "sync_state": True,
            },
            [("1/1/1", (2,))],
            {"state": STATE_ON, "percentage": 66},
        ),
        (  # switch only fan
            {
                "ga_switch": {"write": "1/1/0", "state": "1/1/1"},
                "sync_state": True,
            },
            [("1/1/1", True)],
            {"state": STATE_ON, "percentage": None},
        ),
    ],
)
async def test_fan_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    knx_data: dict[str, Any],
    expected_read_response: list[tuple[str, int | tuple[int, ...]]],
    expected_state: dict[str, Any],
) -> None:
    """Test creating a fan."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.FAN,
        entity_data={"name": "test"},
        knx_data=knx_data,
    )
    for address, response in expected_read_response:
        await knx.assert_read(address, response=response)
    knx.assert_state("fan.test", **expected_state)


async def test_fan_ui_load(knx: KNXTestKit) -> None:
    """Test loading a fan from storage."""
    await knx.setup_integration(config_store_fixture="config_store_fan.json")

    await knx.assert_read("1/1/0", response=(2,), ignore_order=True)  # speed step
    await knx.assert_read("1/2/0", response=True, ignore_order=True)  # oscillation
    await knx.assert_read("2/2/0", response=(0xFF,), ignore_order=True)  # speed percent
    knx.assert_state(
        "fan.test_step_oscillate",
        STATE_ON,
        percentage=50,
        oscillating=True,
    )
    knx.assert_state(
        "fan.test_percent",
        STATE_ON,
        percentage=100,
    )
