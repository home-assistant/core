"""Test KNX sensor."""

from typing import Any

import pytest

from homeassistant.components.knx.const import CONF_STATE_ADDRESS, CONF_SYNC_STATE
from homeassistant.components.knx.schema import SensorSchema
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONF_NAME,
    CONF_TYPE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import async_capture_events


async def test_sensor(
    hass: HomeAssistant, knx: KNXTestKit, create_ui_entity: KnxEntityGenerator
) -> None:
    """Test a simple KNX sensor, set up via YAML and UI."""

    # Setup via YAML
    await knx.setup_integration(
        {
            SensorSchema.PLATFORM: {
                CONF_NAME: "yaml_test",
                CONF_STATE_ADDRESS: "1/1/1",
                CONF_TYPE: "current",  # 2-byte unsigned integer
            }
        }
    )

    # Setup via UI
    await create_ui_entity(
        platform=Platform.SENSOR,
        entity_data={"name": "ui_test"},
        knx_data={
            "ga_sensor": {"state": "2/2/2"},
            "value_type": "current",
        },
    )

    # Check initial state
    for entity_id in ("sensor.yaml_test", "sensor.ui_test"):
        assert hass.states.get(entity_id).state is STATE_UNKNOWN

    async def _read_and_assert(
        entity_id: str, group_addr: str, raw: tuple[int, int], expected: str
    ) -> None:
        """Receive KNX read response and assert sensor state."""
        await knx.assert_read(group_addr)
        await knx.receive_response(group_addr, raw)
        assert hass.states.get(entity_id).state == expected

    async def _write_and_assert(
        entity_id: str, group_addr: str, raw: tuple[int, int], expected: str
    ) -> None:
        """Receive KNX write telegram and assert sensor state."""
        await knx.receive_write(group_addr, raw)
        assert hass.states.get(entity_id).state == expected

    # Initialize sensor state via KNX read
    await _read_and_assert("sensor.yaml_test", "1/1/1", (0, 40), "40")
    await _read_and_assert("sensor.ui_test", "2/2/2", (0, 40), "40")

    # Update sensor state via KNX write
    await _write_and_assert("sensor.yaml_test", "1/1/1", (0x03, 0xE8), "1000")
    await _write_and_assert("sensor.ui_test", "2/2/2", (0x03, 0xE8), "1000")

    # No telegram response on GroupValueRead
    await knx.receive_read("1/1/1")
    await knx.receive_read("2/2/2")
    await knx.assert_no_telegram()


async def test_always_callback(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX sensor with always_callback."""

    await knx.setup_integration(
        {
            SensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test_normal",
                    CONF_STATE_ADDRESS: "1/1/1",
                    CONF_SYNC_STATE: False,
                    CONF_TYPE: "percentU8",
                },
                {
                    CONF_NAME: "test_always",
                    CONF_STATE_ADDRESS: "2/2/2",
                    SensorSchema.CONF_ALWAYS_CALLBACK: True,
                    CONF_SYNC_STATE: False,
                    CONF_TYPE: "percentU8",
                },
            ]
        }
    )
    events = async_capture_events(hass, "state_changed")

    # receive initial telegram
    await knx.receive_write("1/1/1", (0x42,))
    await knx.receive_write("2/2/2", (0x42,))
    assert len(events) == 2

    # receive second telegram with identical payload
    # always_callback shall force state_changed event
    await knx.receive_write("1/1/1", (0x42,))
    await knx.receive_write("2/2/2", (0x42,))
    assert len(events) == 3

    # receive telegram with different payload
    await knx.receive_write("1/1/1", (0xFA,))
    await knx.receive_write("2/2/2", (0xFA,))
    assert len(events) == 5

    # receive telegram with second payload again
    # always_callback shall force state_changed event
    await knx.receive_write("1/1/1", (0xFA,))
    await knx.receive_write("2/2/2", (0xFA,))
    assert len(events) == 6


async def test_sensor_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a sensor via the websocket api."""
    await knx.setup_integration({})
    await create_ui_entity(
        platform=Platform.SENSOR,
        entity_data={
            "name": "uitest",
            "entity_category": "diagnostic",
        },
        knx_data={
            "ga_sensor": {"state": "1/1/1"},
            "value_type": "percentU8",
        },
    )

    state = hass.states.get("sensor.uitest")
    assert state.state is STATE_UNKNOWN

    await knx.assert_read("1/1/1")
    await knx.receive_write("1/1/1", (0x42,))


@pytest.mark.parametrize(
    "test_config",
    [
        # Basic example
        {
            "entity_config": {
                "name": "uitest_basic",
            },
            "knx_data": {
                "ga_sensor": {"state": "1/1/1"},
                "value_type": "percentU8",
            },
        },
        # Advanced example
        {
            "entity_config": {
                "name": "uitest_advanced",
                "entity_category": "diagnostic",
                "device_class": "humidity",
                "state_class": "measurement",
            },
            "knx_data": {
                "ga_sensor": {"state": "2/2/2"},
                "value_type": "percentU8",
                "always_callback": True,
                "sync_state": "every 5",
            },
        },
    ],
)
async def test_sensor_ui_create2(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    test_config: dict[str, Any],
) -> None:
    """Test creating sensors with various KNX configurations and entity configs."""
    await knx.setup_integration({})

    # load test config
    config = {**(test_config or {})}
    entity_id = f"sensor.{config['entity_config']['name']}"

    # create entity via websocket API
    await create_ui_entity(
        platform=Platform.SENSOR,
        entity_data=config["entity_config"],
        knx_data=config["knx_data"],
    )

    # Retrieve the entity from the entity registry
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity, f"Entity {entity_id} was not created."

    assert (
        entity.original_name == config["entity_config"]["name"]
    ), "Entity name mismatch."

    if "entity_category" in config["entity_config"]:
        assert entity.entity_category == EntityCategory(
            config["entity_config"]["entity_category"]
        ), "Entity category mismatch."

    if "device_class" in config["entity_config"]:
        assert (
            entity.original_device_class
            == SensorDeviceClass(config["entity_config"]["device_class"])
        ), f"Device class mismatch for {entity_id}. Expected: {config['entity_config']['device_class']}, Got: {entity.original_device_class}"

    groupAddress = config["knx_data"]["ga_sensor"]["state"]
    await knx.assert_read(groupAddress)
    await knx.receive_response(groupAddress, 1)
