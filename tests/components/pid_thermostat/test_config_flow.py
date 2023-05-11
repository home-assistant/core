"""Test the PID thermostat config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.pid_controller.const import (
    CONF_CYCLE_TIME,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
)
from homeassistant.components.pid_thermostat.const import (
    CONF_AC_MODE,
    CONF_HEATER,
    CONF_SENSOR,
    DEFAULT_AC_MODE,
    DEFAULT_CYCLE_TIME,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("climate",))
async def test_config_flow(
    hass: HomeAssistant, platform: str
) -> None:  # pylint: disable=W0613
    """Test the config flow."""
    heater = "number.output"
    sensor = "sensor.input"
    hass.state = CoreState.starting

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.pid_thermostat.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "My PID Thermostat", CONF_HEATER: heater, CONF_SENSOR: sensor},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My PID Thermostat"
    assert result["data"] == {}
    expected_config = {
        CONF_NAME: "My PID Thermostat",
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_SENSOR: sensor,
        CONF_HEATER: heater,
        CONF_PID_KP: DEFAULT_PID_KP,
        CONF_PID_KI: DEFAULT_PID_KI,
        CONF_PID_KD: DEFAULT_PID_KD,
        CONF_AC_MODE: DEFAULT_AC_MODE,
    }

    assert result["options"] == expected_config
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == expected_config
    assert config_entry.title == "My PID Thermostat"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize("platform", ("climate",))
async def test_options(hass: HomeAssistant, platform: str) -> None:
    """Test reconfiguring."""
    heater_1 = "number.heater_1"
    heater_2 = "number.heater_2"
    sensor = "sensor.input"
    hass.state = CoreState.starting

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "My PID Thermostat",
            CONF_HEATER: heater_1,
            CONF_SENSOR: sensor,
        },
        title="My PID Thermostat",
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, CONF_HEATER) == heater_1

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_HEATER: heater_2, CONF_SENSOR: sensor}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: "My PID Thermostat",
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_SENSOR: sensor,
        CONF_HEATER: heater_2,
        CONF_PID_KP: DEFAULT_PID_KP,
        CONF_PID_KI: DEFAULT_PID_KI,
        CONF_PID_KD: DEFAULT_PID_KD,
        CONF_AC_MODE: DEFAULT_AC_MODE,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        CONF_NAME: "My PID Thermostat",
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_SENSOR: sensor,
        CONF_HEATER: heater_2,
        CONF_PID_KP: DEFAULT_PID_KP,
        CONF_PID_KI: DEFAULT_PID_KI,
        CONF_PID_KD: DEFAULT_PID_KD,
        CONF_AC_MODE: DEFAULT_AC_MODE,
    }
    assert config_entry.title == "My PID Thermostat"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get(f"{platform}.my_pid_thermostat")
    assert state.state == "off"
