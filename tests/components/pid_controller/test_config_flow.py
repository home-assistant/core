"""Test the PID Controller config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
)
from homeassistant.components.pid_controller.const import (
    CONF_CYCLE_TIME,
    CONF_INPUT1,
    CONF_OUTPUT,
    CONF_PID_DIR,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    CONF_STEP,
    DEFAULT_CYCLE_TIME,
    DEFAULT_MODE,
    DEFAULT_PID_DIR,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DOMAIN,
)
from homeassistant.const import CONF_MAXIMUM, CONF_MINIMUM, CONF_MODE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("number",))
async def test_config_flow(
    hass: HomeAssistant, platform: str
) -> None:  # pylint: disable=W0613
    """Test the config flow."""
    output = "number.output"
    input = "sensor.input1"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.pid_controller.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "My PID Controller", CONF_OUTPUT: output, CONF_INPUT1: input},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My PID Controller"
    assert result["data"] == {}
    expected_config = {
        CONF_NAME: "My PID Controller",
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_INPUT1: input,
        #        CONF_INPUT2: "",
        CONF_OUTPUT: output,
        CONF_PID_KP: DEFAULT_PID_KP,
        CONF_PID_KI: DEFAULT_PID_KI,
        CONF_PID_KD: DEFAULT_PID_KD,
        CONF_PID_DIR: DEFAULT_PID_DIR,
        CONF_MINIMUM: DEFAULT_MIN_VALUE,
        CONF_MAXIMUM: DEFAULT_MAX_VALUE,
        CONF_STEP: DEFAULT_STEP,
        CONF_MODE: DEFAULT_MODE,
        #        CONF_UNIQUE_ID: None
    }

    assert result["options"] == expected_config
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == expected_config
    assert config_entry.title == "My PID Controller"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize("platform", ("number",))
async def test_options(hass: HomeAssistant, platform: str) -> None:
    """Test reconfiguring."""
    output_1 = "number.output_1"
    output_2 = "number.output_2"
    input = "sensor.input"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "My PID Controller",
            CONF_OUTPUT: output_1,
            CONF_INPUT1: input,
        },
        title="My PID Controller",
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, CONF_OUTPUT) == output_1

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_OUTPUT: output_2, CONF_INPUT1: input}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: "My PID Controller",
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_INPUT1: input,
        CONF_OUTPUT: output_2,
        CONF_PID_KP: DEFAULT_PID_KP,
        CONF_PID_KI: DEFAULT_PID_KI,
        CONF_PID_KD: DEFAULT_PID_KD,
        CONF_PID_DIR: DEFAULT_PID_DIR,
        CONF_MINIMUM: DEFAULT_MIN_VALUE,
        CONF_MAXIMUM: DEFAULT_MAX_VALUE,
        CONF_STEP: DEFAULT_STEP,
        CONF_MODE: DEFAULT_MODE,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        CONF_NAME: "My PID Controller",
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_INPUT1: input,
        CONF_OUTPUT: output_2,
        CONF_PID_KP: DEFAULT_PID_KP,
        CONF_PID_KI: DEFAULT_PID_KI,
        CONF_PID_KD: DEFAULT_PID_KD,
        CONF_PID_DIR: DEFAULT_PID_DIR,
        CONF_MINIMUM: DEFAULT_MIN_VALUE,
        CONF_MAXIMUM: DEFAULT_MAX_VALUE,
        CONF_STEP: DEFAULT_STEP,
        CONF_MODE: DEFAULT_MODE,
    }
    assert config_entry.title == "My PID Controller"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get(f"{platform}.my_pid_controller")
    assert state.state == "0.0"
