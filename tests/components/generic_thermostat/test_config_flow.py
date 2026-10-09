"""Test the generic hygrostat config flow."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.climate import PRESET_AWAY
from homeassistant.components.generic_thermostat.config_flow import _validate_config
from homeassistant.components.generic_thermostat.const import (
    CONF_AC_MODE,
    CONF_COLD_TOLERANCE,
    CONF_HEATER,
    CONF_HOT_TOLERANCE,
    CONF_KEEP_ALIVE,
    CONF_MAX_DUR,
    CONF_MAX_TEMP,
    CONF_MIN_DUR,
    CONF_MIN_TEMP,
    CONF_PRESETS,
    CONF_SENSOR,
    DOMAIN,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    STATE_OFF,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowError
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from tests.common import MockConfigEntry

SNAPSHOT_FLOW_PROPS = props("type", "title", "result", "error")


async def test_config_flow(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the config flow."""
    with patch(
        "homeassistant.components.generic_thermostat.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result == snapshot(name="init", include=SNAPSHOT_FLOW_PROPS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My thermostat",
                CONF_HEATER: "switch.run",
                CONF_SENSOR: "sensor.temperature",
                CONF_AC_MODE: False,
                CONF_COLD_TOLERANCE: 0.3,
                CONF_HOT_TOLERANCE: 0.3,
            },
        )
        assert result == snapshot(name="presets", include=SNAPSHOT_FLOW_PROPS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PRESETS[PRESET_AWAY]: 20,
            },
        )
        assert result == snapshot(name="create_entry", include=SNAPSHOT_FLOW_PROPS)

        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.title == "My thermostat"


async def test_options(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test reconfiguring."""

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "My thermostat",
            CONF_HEATER: "switch.run",
            CONF_SENSOR: "sensor.temperature",
            CONF_AC_MODE: False,
            CONF_COLD_TOLERANCE: 0.3,
            CONF_HOT_TOLERANCE: 0.3,
            CONF_KEEP_ALIVE: {"seconds": 60},
            CONF_PRESETS[PRESET_AWAY]: 20,
        },
        title="My dehumidifier",
    )
    config_entry.add_to_hass(hass)

    hass.states.async_set(
        "sensor.temperature",
        "15",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
    )
    hass.states.async_set("switch.run", STATE_OFF)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # check that it is setup
    await hass.async_block_till_done()
    assert hass.states.get("climate.my_thermostat") == snapshot(name="with_away")

    # remove away preset
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result == snapshot(name="init", include=SNAPSHOT_FLOW_PROPS)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HEATER: "switch.run",
            CONF_SENSOR: "sensor.temperature",
            CONF_AC_MODE: False,
            CONF_COLD_TOLERANCE: 0.3,
            CONF_HOT_TOLERANCE: 0.3,
        },
    )
    assert result == snapshot(name="presets", include=SNAPSHOT_FLOW_PROPS)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result == snapshot(name="create_entry", include=SNAPSHOT_FLOW_PROPS)

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    assert hass.states.get("climate.my_thermostat") == snapshot(name="without_away")


async def test_config_flow_preset_accepts_float(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the config flow with preset is a float."""
    with patch(
        "homeassistant.components.generic_thermostat.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result == snapshot(name="init", include=SNAPSHOT_FLOW_PROPS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My thermostat",
                CONF_HEATER: "switch.run",
                CONF_SENSOR: "sensor.temperature",
                CONF_AC_MODE: False,
                CONF_COLD_TOLERANCE: 0.3,
                CONF_HOT_TOLERANCE: 0.3,
            },
        )
        assert result == snapshot(name="presets", include=SNAPSHOT_FLOW_PROPS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PRESETS[PRESET_AWAY]: 10.4,
            },
        )
        assert result == snapshot(name="create_entry", include=SNAPSHOT_FLOW_PROPS)

        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    assert result["options"] == {
        "ac_mode": False,
        "away_temp": 10.4,
        "cold_tolerance": 0.3,
        "heater": "switch.run",
        "hot_tolerance": 0.3,
        "name": "My thermostat",
        "target_sensor": "sensor.temperature",
    }


async def test_config_flow_with_keep_alive(hass: HomeAssistant) -> None:
    """Test the config flow when keep_alive is set."""
    with patch(
        "homeassistant.components.generic_thermostat.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        # Keep_alive input data for test
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My thermostat",
                CONF_HEATER: "switch.run",
                CONF_SENSOR: "sensor.temperature",
                CONF_AC_MODE: False,
                CONF_COLD_TOLERANCE: 0.3,
                CONF_HOT_TOLERANCE: 0.3,
                CONF_KEEP_ALIVE: {"seconds": 60},
            },
        )

        # Complete config flow
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PRESETS[PRESET_AWAY]: 21,
            },
        )

        assert result["type"] == "create_entry"

        val = result["options"].get(CONF_KEEP_ALIVE)
        assert val is not None
        assert isinstance(val, dict)
        assert val == {"seconds": 60}

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_validate_config_min_max_duration() -> None:
    """Test _validate_config with min and max cycle duration validation."""
    # Test valid case: min_dur < max_dur
    user_input = {
        CONF_MIN_DUR: {"seconds": 30},
        CONF_MAX_DUR: {"minutes": 1},
    }
    result = await _validate_config(None, user_input)
    assert result == user_input

    # Test invalid case: min_dur >= max_dur
    user_input_invalid = {
        CONF_MIN_DUR: {"minutes": 2},
        CONF_MAX_DUR: {"minutes": 1},
    }
    with pytest.raises(SchemaFlowError) as exc_info:
        await _validate_config(None, user_input_invalid)
    assert str(exc_info.value) == "min_max_runtime"

    # Test equal durations (should fail)
    user_input_equal = {
        CONF_MIN_DUR: {"minutes": 1},
        CONF_MAX_DUR: {"minutes": 1},
    }
    with pytest.raises(SchemaFlowError) as exc_info:
        await _validate_config(None, user_input_equal)
    assert str(exc_info.value) == "min_max_runtime"

    # Test without both durations (should pass)
    user_input_partial = {
        CONF_MIN_DUR: {"seconds": 30},
    }
    result = await _validate_config(None, user_input_partial)
    assert result == user_input_partial


@pytest.mark.parametrize(
    ("units", "user_input"),
    [
        pytest.param(
            METRIC_SYSTEM, {CONF_MIN_TEMP: 15, CONF_MAX_TEMP: 28}, id="min_below_max"
        ),
        pytest.param(
            METRIC_SYSTEM, {CONF_MIN_TEMP: 20, CONF_MAX_TEMP: 20}, id="min_equals_max"
        ),
        pytest.param(METRIC_SYSTEM, {CONF_MIN_TEMP: 20}, id="only_min"),
        pytest.param(METRIC_SYSTEM, {CONF_MAX_TEMP: 30}, id="only_max"),
        pytest.param(
            US_CUSTOMARY_SYSTEM, {CONF_MIN_TEMP: 50}, id="only_min_fahrenheit"
        ),
    ],
)
async def test_validate_config_min_max_temp_valid(
    hass: HomeAssistant, units: UnitSystem, user_input: dict[str, float]
) -> None:
    """Test _validate_config accepts a minimum temperature up to the maximum."""
    hass.config.units = units
    handler = MagicMock()
    handler.parent_handler.hass = hass

    assert await _validate_config(handler, user_input) == user_input


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param({CONF_MIN_TEMP: 28, CONF_MAX_TEMP: 15}, id="min_above_max"),
        pytest.param({CONF_MIN_TEMP: 40}, id="min_above_default_max"),
        pytest.param({CONF_MAX_TEMP: 0}, id="max_below_default_min"),
    ],
)
async def test_validate_config_min_temp_above_max_temp(
    hass: HomeAssistant, user_input: dict[str, float]
) -> None:
    """Test _validate_config rejects a minimum temperature above the maximum."""
    handler = MagicMock()
    handler.parent_handler.hass = hass

    with pytest.raises(SchemaFlowError) as exc_info:
        await _validate_config(handler, user_input)
    assert str(exc_info.value) == "min_max_temp"
