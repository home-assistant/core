"""Test the generic hygrostat config flow."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.climate import PRESET_AWAY
from homeassistant.components.generic_thermostat.const import (
    CONF_AC_MODE,
    CONF_COLD_TOLERANCE,
    CONF_HEATER,
    CONF_HOT_TOLERANCE,
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
