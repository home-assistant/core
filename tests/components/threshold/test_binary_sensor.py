"""The test for the threshold sensor platform."""

import pytest

from homeassistant.components.threshold.const import (
    ATTR_HYSTERESIS,
    ATTR_LOWER,
    ATTR_POSITION,
    ATTR_SENSOR_VALUE,
    ATTR_TYPE,
    ATTR_UPPER,
    CONF_HYSTERESIS,
    CONF_LOWER,
    CONF_UPPER,
    DOMAIN,
    POSITION_ABOVE,
    POSITION_BELOW,
    POSITION_IN_RANGE,
    POSITION_UNKNOWN,
    TYPE_LOWER,
    TYPE_RANGE,
    TYPE_UPPER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("vals", "expected_position", "expected_state"),
    [
        ([15], POSITION_BELOW, STATE_OFF),  # at threshold
        ([15, 16], POSITION_ABOVE, STATE_ON),
        ([15, 16, 14], POSITION_BELOW, STATE_OFF),
        ([15, 16, 14, 15], POSITION_BELOW, STATE_OFF),  # below -> threshold
        ([15, 16, 14, 15, "cat"], POSITION_UNKNOWN, STATE_UNKNOWN),
        ([15, 16, 14, 15, "cat", 15], POSITION_BELOW, STATE_OFF),
        ([15, None], POSITION_UNKNOWN, STATE_UNKNOWN),
    ],
)
async def test_sensor_upper(
    hass: HomeAssistant,
    vals: list[float | str | None],
    expected_position: str,
    expected_state: str,
) -> None:
    """Test if source is above threshold."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_UPPER: "15",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes[ATTR_UPPER] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes[ATTR_HYSTERESIS] == 0.0
    assert state.attributes[ATTR_TYPE] == TYPE_UPPER

    for val in vals:
        hass.states.async_set("sensor.test_monitored", val)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_POSITION] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("vals", "expected_position", "expected_state"),
    [
        ([15], POSITION_ABOVE, STATE_OFF),  # at threshold
        ([15, 16], POSITION_ABOVE, STATE_OFF),
        ([15, 16, 14], POSITION_BELOW, STATE_ON),
        ([15, 16, 14, 15], POSITION_BELOW, STATE_ON),
        ([15, 16, 14, 15, "cat"], POSITION_UNKNOWN, STATE_UNKNOWN),
        ([15, 16, 14, 15, "cat", 15], POSITION_ABOVE, STATE_OFF),
        ([15, None], POSITION_UNKNOWN, STATE_UNKNOWN),
    ],
)
async def test_sensor_lower(
    hass: HomeAssistant,
    vals: list[float | str | None],
    expected_position: str,
    expected_state: str,
) -> None:
    """Test if source is below threshold."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_LOWER: "15",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes[ATTR_LOWER] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes[ATTR_HYSTERESIS] == 0.0
    assert state.attributes[ATTR_TYPE] == TYPE_LOWER

    for val in vals:
        hass.states.async_set("sensor.test_monitored", val)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_POSITION] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("vals", "expected_position", "expected_state"),
    [
        ([17.5], POSITION_BELOW, STATE_OFF),  # threshold + hysteresis
        ([17.5, 12.5], POSITION_BELOW, STATE_OFF),  # threshold - hysteresis
        ([17.5, 12.5, 20], POSITION_ABOVE, STATE_ON),
        ([17.5, 12.5, 20, 13], POSITION_ABOVE, STATE_ON),
        ([17.5, 12.5, 20, 13, 12], POSITION_BELOW, STATE_OFF),
        ([17.5, 12.5, 20, 13, 12, 17], POSITION_BELOW, STATE_OFF),
        ([17.5, 12.5, 20, 13, 12, 17, 18], POSITION_ABOVE, STATE_ON),
        ([17.5, 12.5, 20, 13, 12, 17, 18, "cat"], POSITION_UNKNOWN, STATE_UNKNOWN),
        ([17.5, 12.5, 20, 13, 12, 17, 18, "cat", 18], POSITION_ABOVE, STATE_ON),
        ([18, None], POSITION_UNKNOWN, STATE_UNKNOWN),
        # below within -> above
        ([14, 17.6], POSITION_ABOVE, STATE_ON),
        # above within -> below
        ([16, 12.4], POSITION_BELOW, STATE_OFF),
        # below within -> above within
        ([14, 16], POSITION_BELOW, STATE_OFF),
        # above within -> below within
        ([16, 14], POSITION_BELOW, STATE_OFF),
        # above -> above within -> below within
        ([20, 16, 14], POSITION_ABOVE, STATE_ON),
        # below -> below within -> above within
        ([10, 14, 16], POSITION_BELOW, STATE_OFF),
    ],
)
async def test_sensor_upper_hysteresis(
    hass: HomeAssistant,
    vals: list[float | str | None],
    expected_position: str,
    expected_state: str,
) -> None:
    """Test if source is above threshold using hysteresis."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_UPPER: "15",
            CONF_HYSTERESIS: "2.5",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes[ATTR_UPPER] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes[ATTR_HYSTERESIS] == 2.5
    assert state.attributes[ATTR_TYPE] == TYPE_UPPER

    for val in vals:
        hass.states.async_set("sensor.test_monitored", val)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_POSITION] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("vals", "expected_position", "expected_state"),
    [
        ([17.5], POSITION_ABOVE, STATE_OFF),  # threshold + hysteresis
        ([17.5, 12.5], POSITION_ABOVE, STATE_OFF),  # threshold - hysteresis
        ([17.5, 12.5, 20], POSITION_ABOVE, STATE_OFF),
        ([17.5, 12.5, 20, 13], POSITION_ABOVE, STATE_OFF),
        ([17.5, 12.5, 20, 13, 12], POSITION_BELOW, STATE_ON),
        ([17.5, 12.5, 20, 13, 12, 17], POSITION_BELOW, STATE_ON),
        ([17.5, 12.5, 20, 13, 12, 17, 18], POSITION_ABOVE, STATE_OFF),
        ([17.5, 12.5, 20, 13, 12, 17, 18, "cat"], POSITION_UNKNOWN, STATE_UNKNOWN),
        ([17.5, 12.5, 20, 13, 12, 17, 18, "cat", 18], POSITION_ABOVE, STATE_OFF),
        ([18, None], POSITION_UNKNOWN, STATE_UNKNOWN),
        # below within -> above
        ([14, 17.6], POSITION_ABOVE, STATE_OFF),
        # above within -> below
        ([16, 12.4], POSITION_BELOW, STATE_ON),
        # below within -> above within
        ([14, 16], POSITION_ABOVE, STATE_OFF),
        # above within -> below within
        ([16, 14], POSITION_ABOVE, STATE_OFF),
        # above -> above within -> below within
        ([20, 16, 14], POSITION_ABOVE, STATE_OFF),
        # below -> below within -> above within
        ([10, 14, 16], POSITION_BELOW, STATE_ON),
    ],
)
async def test_sensor_lower_hysteresis(
    hass: HomeAssistant,
    vals: list[float | str | None],
    expected_position: str,
    expected_state: str,
) -> None:
    """Test if source is below threshold using hysteresis."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_LOWER: "15",
            CONF_HYSTERESIS: "2.5",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes[ATTR_LOWER] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes[ATTR_HYSTERESIS] == 2.5
    assert state.attributes[ATTR_TYPE] == TYPE_LOWER

    for val in vals:
        hass.states.async_set("sensor.test_monitored", val)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_POSITION] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("vals", "expected_position", "expected_state"),
    [
        ([10], POSITION_IN_RANGE, STATE_ON),  # at lower threshold
        ([10, 20], POSITION_IN_RANGE, STATE_ON),  # lower threshold -> upper threshold
        ([10, 20, 16], POSITION_IN_RANGE, STATE_ON),
        ([10, 20, 16, 9], POSITION_BELOW, STATE_OFF),
        ([10, 20, 16, 9, 21], POSITION_ABOVE, STATE_OFF),
        ([10, 20, 16, 9, 21, "cat"], POSITION_UNKNOWN, STATE_UNKNOWN),
        ([10, 20, 16, 9, 21, "cat", 21], POSITION_ABOVE, STATE_OFF),
        ([21, None], POSITION_UNKNOWN, STATE_UNKNOWN),
        # upper threshold -> lower threshold
        ([20, 10], POSITION_IN_RANGE, STATE_ON),
        # in-range -> upper threshold
        ([15, 20], POSITION_IN_RANGE, STATE_ON),
        # in-range -> lower threshold
        ([15, 10], POSITION_IN_RANGE, STATE_ON),
        # below -> above
        ([5, 25], POSITION_ABOVE, STATE_OFF),
        # above -> below
        ([25, 5], POSITION_BELOW, STATE_OFF),
        # in-range -> above
        ([15, 25], POSITION_ABOVE, STATE_OFF),
        # in-range -> below
        ([15, 5], POSITION_BELOW, STATE_OFF),
    ],
)
async def test_sensor_in_range_no_hysteresis(
    hass: HomeAssistant,
    vals: list[float | str | None],
    expected_position: str,
    expected_state: str,
) -> None:
    """Test if source is within the range."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_LOWER: "10",
            CONF_UPPER: "20",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes[ATTR_LOWER] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes[ATTR_UPPER] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes[ATTR_HYSTERESIS] == 0.0
    assert state.attributes[ATTR_TYPE] == TYPE_RANGE

    for val in vals:
        hass.states.async_set("sensor.test_monitored", val)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_POSITION] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("vals", "expected_position", "expected_state"),
    [
        ([12], POSITION_IN_RANGE, STATE_ON),  # lower threshold + hysteresis
        ([12, 22], POSITION_IN_RANGE, STATE_ON),  # upper threshold + hysteresis
        ([12, 22, 18], POSITION_IN_RANGE, STATE_ON),  # upper threshold - hysteresis
        ([12, 22, 18, 16], POSITION_IN_RANGE, STATE_ON),
        ([12, 22, 18, 16, 8], POSITION_IN_RANGE, STATE_ON),
        ([12, 22, 18, 16, 8, 7], POSITION_BELOW, STATE_OFF),
        ([12, 22, 18, 16, 8, 7, 12], POSITION_BELOW, STATE_OFF),
        ([12, 22, 18, 16, 8, 7, 12, 13], POSITION_IN_RANGE, STATE_ON),
        ([12, 22, 18, 16, 8, 7, 12, 13, 22], POSITION_IN_RANGE, STATE_ON),
        ([12, 22, 18, 16, 8, 7, 12, 13, 22, 23], POSITION_ABOVE, STATE_OFF),
        ([12, 22, 18, 16, 8, 7, 12, 13, 22, 23, 18], POSITION_ABOVE, STATE_OFF),
        ([12, 22, 18, 16, 8, 7, 12, 13, 22, 23, 18, 17], POSITION_IN_RANGE, STATE_ON),
        (
            [12, 22, 18, 16, 8, 7, 12, 13, 22, 23, 18, 17, "cat"],
            POSITION_UNKNOWN,
            STATE_UNKNOWN,
        ),
        (
            [12, 22, 18, 16, 8, 7, 12, 13, 22, 23, 18, 17, "cat", 17],
            POSITION_IN_RANGE,
            STATE_ON,
        ),
        ([17, None], POSITION_UNKNOWN, STATE_UNKNOWN),
        # upper threshold -> lower threshold
        ([20, 10], POSITION_IN_RANGE, STATE_ON),
        # in-range -> upper threshold
        ([15, 20], POSITION_IN_RANGE, STATE_ON),
        # in-range -> lower threshold
        ([15, 10], POSITION_IN_RANGE, STATE_ON),
        # below -> above
        ([5, 25], POSITION_ABOVE, STATE_OFF),
        # above -> below
        ([25, 5], POSITION_BELOW, STATE_OFF),
        # in-range -> above
        ([15, 25], POSITION_ABOVE, STATE_OFF),
        # in-range -> below
        ([15, 5], POSITION_BELOW, STATE_OFF),
        # below -> lower threshold
        ([5, 10], POSITION_BELOW, STATE_OFF),
        # below -> in-range -> lower threshold
        ([5, 15, 10], POSITION_IN_RANGE, STATE_ON),
        # above -> upper threshold
        ([25, 20], POSITION_ABOVE, STATE_OFF),
        # above -> in-range -> upper threshold
        ([25, 15, 20], POSITION_IN_RANGE, STATE_ON),
        ([15, 22.1], POSITION_ABOVE, STATE_OFF),  # in-range -> above hysteresis edge
        ([15, 7.9], POSITION_BELOW, STATE_OFF),  # in-range -> below hysteresis edge
        ([7, 11.9], POSITION_BELOW, STATE_OFF),
        ([23, 18.1], POSITION_ABOVE, STATE_OFF),
    ],
)
async def test_sensor_in_range_with_hysteresis(
    hass: HomeAssistant,
    vals: list[float | str | None],
    expected_position: str,
    expected_state: str,
) -> None:
    """Test if source is within the range."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_LOWER: "10",
            CONF_UPPER: "20",
            CONF_HYSTERESIS: "2",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes[ATTR_LOWER] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes[ATTR_UPPER] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes[ATTR_HYSTERESIS] == 2.0
    assert state.attributes[ATTR_TYPE] == TYPE_RANGE

    for val in vals:
        hass.states.async_set("sensor.test_monitored", val)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_POSITION] == expected_position
    assert state.state == expected_state


async def test_sensor_in_range_unknown_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if source is within the range."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_LOWER: "10",
            CONF_UPPER: "20",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.test_monitored",
        16,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes[ATTR_SENSOR_VALUE] == 16
    assert state.attributes[ATTR_POSITION] == POSITION_IN_RANGE
    assert state.attributes[ATTR_LOWER] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes[ATTR_UPPER] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes[ATTR_HYSTERESIS] == 0.0
    assert state.attributes[ATTR_TYPE] == TYPE_RANGE
    assert state.state == STATE_ON

    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_POSITION] == POSITION_UNKNOWN
    assert state.state == STATE_UNKNOWN

    hass.states.async_set("sensor.test_monitored", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_POSITION] == POSITION_UNKNOWN
    assert state.state == STATE_UNKNOWN

    assert "State is not numerical" not in caplog.text


async def test_sensor_lower_zero_threshold(hass: HomeAssistant) -> None:
    """Test if a lower threshold of zero is set."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_LOWER: "0",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", 16)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_TYPE] == TYPE_LOWER
    assert state.attributes[ATTR_LOWER] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.state == STATE_OFF

    hass.states.async_set("sensor.test_monitored", -3)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.state == STATE_ON


async def test_sensor_upper_zero_threshold(hass: HomeAssistant) -> None:
    """Test if an upper threshold of zero is set."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_UPPER: "0",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", -10)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_TYPE] == TYPE_UPPER
    assert state.attributes[ATTR_UPPER] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.state == STATE_OFF

    hass.states.async_set("sensor.test_monitored", 2)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.state == STATE_ON


async def test_sensor_no_lower_upper(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if no lower or upper has been provided."""
    config = {
        Platform.BINARY_SENSOR: {
            CONF_PLATFORM: "threshold",
            CONF_ENTITY_ID: "sensor.test_monitored",
        }
    }

    await async_setup_component(hass, Platform.BINARY_SENSOR, config)
    await hass.async_block_till_done()

    assert "Lower or Upper thresholds are not provided" in caplog.text


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Threshold."""
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)
    source_device_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("sensor", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    utility_meter_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "sensor.test_source",
            CONF_HYSTERESIS: 0.0,
            CONF_LOWER: -2.0,
            CONF_NAME: "Threshold",
            CONF_UPPER: None,
        },
        title="Threshold",
    )

    utility_meter_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(utility_meter_config_entry.entry_id)
    await hass.async_block_till_done()

    utility_meter_entity = entity_registry.async_get("binary_sensor.threshold")
    assert utility_meter_entity is not None
    assert utility_meter_entity.device_id == source_entity.device_id
