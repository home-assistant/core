"""The test for the threshold sensor platform."""

import pytest

from homeassistant.components.threshold.const import (
    CONF_HYSTERESIS,
    CONF_LOWER,
    CONF_UPPER,
    DOMAIN,
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
    ("from_val", "to_val", "expected_position", "expected_state"),
    [
        (None, 15, "below", STATE_OFF),  # at threshold
        (15, 16, "above", STATE_ON),
        (16, 14, "below", STATE_OFF),
        (14, 15, "below", STATE_OFF),
        (15, "cat", "unknown", STATE_UNKNOWN),
        ("cat", 15, "below", STATE_OFF),
        (15, None, "unknown", STATE_UNKNOWN),
    ],
)
async def test_sensor_upper(
    hass: HomeAssistant,
    from_val: float | str | None,
    to_val: float | str,
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

    hass.states.async_set("sensor.test_monitored", from_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes["upper"] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["type"] == "upper"

    hass.states.async_set("sensor.test_monitored", to_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("from_val", "to_val", "expected_position", "expected_state"),
    [
        (None, 15, "above", STATE_OFF),  # at threshold
        (15, 16, "above", STATE_OFF),
        (16, 14, "below", STATE_ON),
        (14, 15, "below", STATE_ON),
        (15, "cat", "unknown", STATE_UNKNOWN),
        ("cat", 15, "above", STATE_OFF),
        (15, None, "unknown", STATE_UNKNOWN),
    ],
)
async def test_sensor_lower(
    hass: HomeAssistant,
    from_val: float | str | None,
    to_val: float | str,
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

    hass.states.async_set("sensor.test_monitored", from_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes["lower"] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["type"] == "lower"

    hass.states.async_set("sensor.test_monitored", to_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("from_val", "to_val", "expected_position", "expected_state"),
    [
        (None, 17.5, "below", STATE_OFF),  # threshold + hysteresis
        (17.5, 12.5, "below", STATE_OFF),  # threshold - hysteresis
        (12.5, 20, "above", STATE_ON),
        (20, 13, "above", STATE_ON),
        (13, 12, "below", STATE_OFF),
        (12, 17, "below", STATE_OFF),
        (17, 18, "above", STATE_ON),
        (18, "cat", "unknown", STATE_UNKNOWN),
        ("cat", 18, "above", STATE_ON),
        (18, None, "unknown", STATE_UNKNOWN),
    ],
)
async def test_sensor_upper_hysteresis(
    hass: HomeAssistant,
    from_val: float | str | None,
    to_val: float | str,
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

    hass.states.async_set("sensor.test_monitored", from_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes["upper"] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes["hysteresis"] == 2.5
    assert state.attributes["type"] == "upper"

    hass.states.async_set("sensor.test_monitored", to_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("from_val", "to_val", "expected_position", "expected_state"),
    [
        (None, 17.5, "above", STATE_OFF),  # threshold + hysteresis
        (17.5, 12.5, "above", STATE_OFF),  # threshold - hysteresis
        (12.5, 20, "above", STATE_OFF),
        (20, 13, "above", STATE_OFF),
        (13, 12, "below", STATE_ON),
        (12, 17, "below", STATE_ON),
        (17, 18, "above", STATE_OFF),
        (18, "cat", "unknown", STATE_UNKNOWN),
        ("cat", 18, "above", STATE_OFF),
        (18, None, "unknown", STATE_UNKNOWN),
    ],
)
async def test_sensor_lower_hysteresis(
    hass: HomeAssistant,
    from_val: float | str | None,
    to_val: float | str,
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

    hass.states.async_set("sensor.test_monitored", from_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes["lower"] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes["hysteresis"] == 2.5
    assert state.attributes["type"] == "lower"

    hass.states.async_set("sensor.test_monitored", to_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("from_val", "to_val", "expected_position", "expected_state"),
    [
        (None, 10, "in_range", STATE_ON),  # at lower threshold
        (10, 20, "in_range", STATE_ON),  # at upper threshold
        (20, 16, "in_range", STATE_ON),
        (16, 9, "below", STATE_OFF),
        (9, 21, "above", STATE_OFF),
        (21, "cat", "unknown", STATE_UNKNOWN),
        ("cat", 21, "above", STATE_OFF),
        (21, None, "unknown", STATE_UNKNOWN),
    ],
)
async def test_sensor_in_range_no_hysteresis(
    hass: HomeAssistant,
    from_val: float | str | None,
    to_val: float | str,
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

    hass.states.async_set("sensor.test_monitored", from_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes["lower"] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes["upper"] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["type"] == "range"

    hass.states.async_set("sensor.test_monitored", to_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == expected_position
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("from_val", "to_val", "expected_position", "expected_state"),
    [
        (None, 12, "in_range", STATE_ON),  # lower threshold + hysteresis
        (12, 22, "in_range", STATE_ON),  # upper threshold + hysteresis
        (22, 18, "in_range", STATE_ON),  # upper threshold - hysteresis
        (18, 16, "in_range", STATE_ON),
        (16, 8, "in_range", STATE_ON),
        (8, 7, "below", STATE_OFF),
        (7, 12, "below", STATE_OFF),
        (12, 13, "in_range", STATE_ON),
        (13, 22, "in_range", STATE_ON),
        (22, 23, "above", STATE_OFF),
        (23, 18, "above", STATE_OFF),
        (18, 17, "in_range", STATE_ON),
        (17, "cat", "unknown", STATE_UNKNOWN),
        ("cat", 17, "in_range", STATE_ON),
        (17, None, "unknown", STATE_UNKNOWN),
    ],
)
async def test_sensor_in_range_with_hysteresis(
    hass: HomeAssistant,
    from_val: float | str | None,
    to_val: float | str,
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

    hass.states.async_set("sensor.test_monitored", from_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes[ATTR_ENTITY_ID] == "sensor.test_monitored"
    assert state.attributes["lower"] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes["upper"] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes["hysteresis"] == 2.0
    assert state.attributes["type"] == "range"

    hass.states.async_set("sensor.test_monitored", to_val)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == expected_position
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
    assert state.attributes["sensor_value"] == 16
    assert state.attributes["position"] == "in_range"
    assert state.attributes["lower"] == float(
        config[Platform.BINARY_SENSOR][CONF_LOWER]
    )
    assert state.attributes["upper"] == float(
        config[Platform.BINARY_SENSOR][CONF_UPPER]
    )
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["type"] == "range"
    assert state.state == STATE_ON

    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == STATE_UNKNOWN

    hass.states.async_set("sensor.test_monitored", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
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
    assert state.attributes["type"] == "lower"
    assert state.attributes["lower"] == float(
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
    assert state.attributes["type"] == "upper"
    assert state.attributes["upper"] == float(
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

    assert "Lower or Upper thresholds not provided" in caplog.text


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
