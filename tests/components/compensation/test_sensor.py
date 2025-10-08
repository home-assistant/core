"""The tests for the integration sensor platform."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.compensation.const import CONF_PRECISION, DOMAIN
from homeassistant.components.compensation.sensor import ATTR_COEFFICIENTS
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    EVENT_STATE_CHANGED,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, get_fixture_path

TEST_OBJECT_ID = "test_compensation"
TEST_ENTITY_ID = "sensor.test_compensation"
TEST_SOURCE = "sensor.uncompensated"

TEST_BASE_CONFIG = {
    "source": TEST_SOURCE,
    "data_points": [
        [1.0, 2.0],
        [2.0, 3.0],
    ],
    "precision": 2,
}
TEST_CONFIG = {
    "name": TEST_OBJECT_ID,
    "unit_of_measurement": "a",
    **TEST_BASE_CONFIG,
}


async def async_setup_compensation(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Do setup of a compensation integration sensor."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {"test": config}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def setup_compensation(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Do setup of a compensation integration sensor."""
    await async_setup_compensation(hass, config)


@pytest.fixture
async def setup_compensation_with_limits(
    hass: HomeAssistant,
    config: dict[str, Any],
    upper: bool,
    lower: bool,
):
    """Do setup of a compensation integration sensor with extra config."""
    await async_setup_compensation(
        hass,
        {
            **config,
            "lower_limit": lower,
            "upper_limit": upper,
        },
    )


@pytest.fixture
async def caplog_setup_text(caplog: pytest.LogCaptureFixture) -> str:
    """Return setup log of integration."""
    return caplog.text


@pytest.mark.parametrize("config", [TEST_CONFIG])
@pytest.mark.usefixtures("setup_compensation")
async def test_linear_state(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test compensation sensor state."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.states.async_set(TEST_SOURCE, 4, {})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None

    assert round(float(state.state), config[CONF_PRECISION]) == 5.0

    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "a"

    coefs = [round(v, 1) for v in state.attributes.get(ATTR_COEFFICIENTS)]
    assert coefs == [1.0, 1.0]

    hass.states.async_set(TEST_SOURCE, "foo", {})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None

    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("config", [{"name": TEST_OBJECT_ID, **TEST_BASE_CONFIG}])
@pytest.mark.usefixtures("setup_compensation")
async def test_attributes_come_from_source(hass: HomeAssistant) -> None:
    """Test compensation sensor state."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.states.async_set(
        TEST_SOURCE,
        4,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == "5.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


@pytest.mark.parametrize("config", [{"attribute": "value", **TEST_CONFIG}])
@pytest.mark.usefixtures("setup_compensation")
async def test_linear_state_from_attribute(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test compensation sensor state that pulls from attribute."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set(TEST_SOURCE, 3, {"value": 4})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None

    assert round(float(state.state), config[CONF_PRECISION]) == 5.0

    coefs = [round(v, 1) for v in state.attributes.get(ATTR_COEFFICIENTS)]
    assert coefs == [1.0, 1.0]

    hass.states.async_set(TEST_SOURCE, 3, {"value": "bar"})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None

    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "config",
    [
        {
            "name": TEST_OBJECT_ID,
            "source": TEST_SOURCE,
            "data_points": [
                [50, 3.3],
                [50, 2.8],
                [50, 2.9],
                [70, 2.3],
                [70, 2.6],
                [70, 2.1],
                [80, 2.5],
                [80, 2.9],
                [80, 2.4],
                [90, 3.0],
                [90, 3.1],
                [90, 2.8],
                [100, 3.3],
                [100, 3.5],
                [100, 3.0],
            ],
            "degree": 2,
            "precision": 3,
        },
    ],
)
@pytest.mark.usefixtures("setup_compensation")
async def test_quadratic_state(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test 3 degree polynominial compensation sensor."""
    hass.states.async_set(TEST_SOURCE, 43.2, {})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)

    assert state is not None

    assert round(float(state.state), config[CONF_PRECISION]) == 3.327


@pytest.mark.parametrize(
    "config",
    [
        {
            "source": TEST_SOURCE,
            "data_points": [
                [0.0, 1.0],
                [0.0, 1.0],
            ],
        },
    ],
)
@pytest.mark.usefixtures("setup_compensation")
async def test_numpy_errors(hass: HomeAssistant, caplog_setup_text) -> None:
    """Tests bad polyfits."""
    assert "invalid value encountered in divide" in caplog_setup_text


async def test_datapoints_greater_than_degree(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests 3 bad data points."""
    config = {
        "compensation": {
            "test": {
                "source": TEST_SOURCE,
                "data_points": [
                    [1.0, 2.0],
                    [2.0, 3.0],
                ],
                "degree": 2,
            },
        }
    }
    await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert "data_points must have at least 3 data_points" in caplog.text


@pytest.mark.parametrize("config", [TEST_CONFIG])
@pytest.mark.usefixtures("setup_compensation")
async def test_new_state_is_none(hass: HomeAssistant) -> None:
    """Tests catch for empty new states."""
    last_changed = hass.states.get(TEST_ENTITY_ID).last_changed
    hass.bus.async_fire(EVENT_STATE_CHANGED, event_data={"entity_id": TEST_SOURCE})
    assert last_changed == hass.states.get(TEST_ENTITY_ID).last_changed


@pytest.mark.parametrize(
    ("lower", "upper"),
    [
        (True, False),
        (False, True),
        (True, True),
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "name": TEST_OBJECT_ID,
            "source": TEST_SOURCE,
            "data_points": [
                [1.0, 0.0],
                [3.0, 2.0],
                [2.0, 1.0],
            ],
            "precision": 2,
            "unit_of_measurement": "a",
        },
    ],
)
@pytest.mark.usefixtures("setup_compensation_with_limits")
async def test_limits(hass: HomeAssistant, lower: bool, upper: bool) -> None:
    """Test compensation sensor state."""
    hass.states.async_set(TEST_SOURCE, 0, {})
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    value = 0.0 if lower else -1.0
    assert float(state.state) == value

    hass.states.async_set(TEST_SOURCE, 5, {})
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    value = 2.0 if upper else 4.0
    assert float(state.state) == value


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (TEST_BASE_CONFIG, "sensor.compensation_sensor_uncompensated"),
        (
            {"attribute": "value", **TEST_BASE_CONFIG},
            "sensor.compensation_sensor_uncompensated_value",
        ),
    ],
)
@pytest.mark.usefixtures("setup_compensation")
async def test_default_name(hass: HomeAssistant, expected: str) -> None:
    """Test default configuration name."""
    assert hass.states.get(expected) is not None


@pytest.mark.parametrize("config", [TEST_CONFIG])
@pytest.mark.parametrize(
    ("source_state", "expected"),
    [(STATE_UNKNOWN, STATE_UNKNOWN), (STATE_UNAVAILABLE, STATE_UNAVAILABLE)],
)
@pytest.mark.usefixtures("setup_compensation")
async def test_non_numerical_states_from_source_entity(
    hass: HomeAssistant, config: dict[str, Any], source_state: str, expected: str
) -> None:
    """Test non-numerical states from source entity."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.states.async_set(TEST_SOURCE, source_state)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == expected

    hass.states.async_set(TEST_SOURCE, 4)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert round(float(state.state), config[CONF_PRECISION]) == 5.0

    hass.states.async_set(TEST_SOURCE, source_state)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == expected


async def test_source_state_none(hass: HomeAssistant) -> None:
    """Test is source sensor state is null and sets state to STATE_UNKNOWN."""
    config = {
        "sensor": [
            {
                "platform": "template",
                "sensors": {
                    "uncompensated": {
                        "value_template": "{{ states.sensor.test_state.state }}"
                    }
                },
            },
        ]
    }
    await async_setup_component(hass, "sensor", config)
    await async_setup_compensation(hass, TEST_CONFIG)

    hass.states.async_set("sensor.test_state", 4)

    await hass.async_block_till_done()
    state = hass.states.get(TEST_SOURCE)
    assert state.state == "4"

    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == "5.0"

    # Force Template Reload
    yaml_path = get_fixture_path("sensor_configuration.yaml", "template")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "template",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Template state gets to None
    state = hass.states.get(TEST_SOURCE)
    assert state is None

    # Filter sensor ignores None state setting state to STATE_UNKNOWN
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN
