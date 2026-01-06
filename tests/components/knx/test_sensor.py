"""Test KNX sensor."""

import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.knx.const import (
    ATTR_SOURCE,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
)
from homeassistant.components.knx.schema import SensorSchema
from homeassistant.components.sensor import (
    CONF_STATE_CLASS as CONF_SENSOR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, CONF_TYPE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import (
    async_capture_events,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)


async def test_sensor(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test simple KNX sensor."""

    await knx.setup_integration(
        {
            SensorSchema.PLATFORM: {
                CONF_NAME: "test",
                CONF_STATE_ADDRESS: "1/1/1",
                CONF_TYPE: "current",  # 2 byte unsigned int
            }
        }
    )
    state = hass.states.get("sensor.test")
    assert state.state is STATE_UNKNOWN

    # StateUpdater initialize state
    await knx.assert_read("1/1/1")
    await knx.receive_response("1/1/1", (0, 40))
    knx.assert_state(
        "sensor.test",
        "40",
        # default values for DPT type "current"
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        unit_of_measurement="mA",
    )

    # update from KNX
    await knx.receive_write("1/1/1", (0x03, 0xE8))
    knx.assert_state("sensor.test", "1000")

    # don't answer to GroupValueRead requests
    await knx.receive_read("1/1/1")
    await knx.assert_no_telegram()


async def test_sensor_restore(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test restoring KNX sensor state."""
    ADDRESS = "2/2/2"
    RAW_FLOAT_21_0 = (0x0C, 0x1A)
    RESTORED_STATE = "21.0"
    RESTORED_STATE_ATTRIBUTES = {ATTR_SOURCE: knx.INDIVIDUAL_ADDRESS}
    fake_state = State(
        "sensor.test", "ignored in favour of native_value", RESTORED_STATE_ATTRIBUTES
    )
    extra_data = {"native_value": RESTORED_STATE, "native_unit_of_measurement": "°C"}
    mock_restore_cache_with_extra_data(hass, [(fake_state, extra_data)])

    await knx.setup_integration(
        {
            SensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    CONF_STATE_ADDRESS: ADDRESS,
                    CONF_TYPE: "temperature",  # 2 byte float
                    CONF_SYNC_STATE: False,
                },
            ]
        }
    )

    # restored state - no read-response due to sync_state False
    knx.assert_state("sensor.test", RESTORED_STATE, **RESTORED_STATE_ATTRIBUTES)
    await knx.assert_telegram_count(0)

    # receiving the restored value from restored source does not trigger state_changed event
    events = async_capture_events(hass, "state_changed")
    await knx.receive_write(ADDRESS, RAW_FLOAT_21_0)
    assert not events


async def test_last_reported(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test KNX sensor properly sets last_reported."""

    await knx.setup_integration(
        {
            SensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    CONF_STATE_ADDRESS: "1/1/1",
                    CONF_SYNC_STATE: False,
                    CONF_TYPE: "percentU8",
                },
            ]
        }
    )
    events = async_capture_events(hass, "state_changed")

    # receive initial telegram
    await knx.receive_write("1/1/1", (0x42,))
    first_reported = hass.states.get("sensor.test").last_reported
    assert len(events) == 1

    # receive second telegram with identical payload
    freezer.tick(1)
    async_fire_time_changed(hass)
    await knx.receive_write("1/1/1", (0x42,))

    assert first_reported != hass.states.get("sensor.test").last_reported
    assert len(events) == 1, events  # last_reported shall not fire state_changed


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


async def test_sensor_yaml_attribute_validation(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    knx: KNXTestKit,
) -> None:
    """Test creating a sensor with invalid unit, state_class or device_class."""
    with caplog.at_level(logging.ERROR):
        await knx.setup_integration(
            {
                SensorSchema.PLATFORM: {
                    CONF_NAME: "test",
                    CONF_STATE_ADDRESS: "1/1/1",
                    CONF_TYPE: "9.001",  # temperature 2 byte float
                    CONF_SENSOR_STATE_CLASS: "total_increasing",  # invalid for temperature
                }
            }
        )
    assert len(caplog.messages) == 2
    record = caplog.records[0]
    assert record.levelname == "ERROR"
    assert (
        "Invalid config for 'knx': State class 'total_increasing' is not valid for device class"
        in record.message
    )

    record = caplog.records[1]
    assert record.levelname == "ERROR"
    assert "Setup failed for 'knx': Invalid config." in record.message

    assert hass.states.get("sensor.test") is None


@pytest.mark.parametrize(
    ("knx_config", "response_payload", "expected_state"),
    [
        (
            {
                "ga_sensor": {
                    "state": "1/1/1",
                    "passive": [],
                    "dpt": "9.001",  # temperature 2 byte float
                },
            },
            (0, 0),
            {
                "state": "0.0",
                "device_class": SensorDeviceClass.TEMPERATURE,
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": "°C",
            },
        ),
        (
            {
                "ga_sensor": {
                    "state": "1/1/1",
                    "passive": [],
                    "dpt": "12",  # generic 4byte uint
                },
                "state_class": "total_increasing",
                "device_class": "energy",
                "unit_of_measurement": "Mcal",
                "sync_state": True,
            },
            (1, 2, 3, 4),
            {
                "state": "16909060",
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
        ),
    ],
)
async def test_sensor_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    knx_config: dict[str, Any],
    response_payload: tuple[int, ...],
    expected_state: dict[str, Any],
) -> None:
    """Test creating a sensor."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SENSOR,
        entity_data={"name": "test"},
        knx_data=knx_config,
    )
    # created entity sends read-request to KNX bus
    await knx.assert_read("1/1/1")
    await knx.receive_response("1/1/1", response_payload)
    knx.assert_state("sensor.test", **expected_state)


async def test_sensor_ui_load(knx: KNXTestKit) -> None:
    """Test loading a sensor from storage."""
    await knx.setup_integration(config_store_fixture="config_store_sensor.json")

    await knx.assert_read("1/1/1", response=(0, 0), ignore_order=True)
    knx.assert_state(
        "sensor.test",
        "0",
        device_class=None,  # 7.600 color temperature has no sensor device class
        state_class="measurement",
        unit_of_measurement="K",
    )


@pytest.mark.parametrize(
    "knx_config",
    [
        (
            {
                "ga_sensor": {
                    "state": "1/1/1",
                    "passive": [],
                    "dpt": "9.001",  # temperature 2 byte float
                },
                "state_class": "totoal_increasing",  # invalid for temperature
            }
        ),
        (
            {
                "ga_sensor": {
                    "state": "1/1/1",
                    "passive": [],
                    "dpt": "12",  # generic 4byte uint
                },
                "state_class": "total_increasing",
                "device_class": "energy",  # requires unit_of_measurement
                "sync_state": True,
            }
        ),
        (
            {
                "ga_sensor": {
                    "state": "1/1/1",
                    "passive": [],
                    "dpt": "9.001",  # temperature 2 byte float
                },
                "state_class": "measurement_angle",  # requires degree unit
                "sync_state": True,
            }
        ),
    ],
)
async def test_sensor_ui_create_attribute_validation(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    knx_config: dict[str, Any],
) -> None:
    """Test creating a sensor with invalid unit, state_class or device_class."""
    await knx.setup_integration()
    with pytest.raises(AssertionError) as err:
        await create_ui_entity(
            platform=Platform.SENSOR,
            entity_data={"name": "test"},
            knx_data=knx_config,
        )
    assert "success" in err.value.args[0]
    assert "error_base" in err.value.args[0]
    assert "path" in err.value.args[0]
