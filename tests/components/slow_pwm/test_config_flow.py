"""Test the Min/Max config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
)
from homeassistant.components.slow_pwm.const import (
    CONF_CYCLE_TIME,
    CONF_MIN_SWITCH_TIME,
    CONF_OUTPUTS,
    CONF_STEP,
    DEFAULT_CYCLE_TIME,
    DEFAULT_MODE,
    DEFAULT_SWITCH_TIME,
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
    outputs = ["switch.output_1", "switch.output_2"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.slow_pwm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "My slow_pwm", CONF_OUTPUTS: outputs},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My slow_pwm"
    assert result["data"] == {}
    expected_config = {
        CONF_OUTPUTS: outputs,
        CONF_NAME: "My slow_pwm",
        CONF_MINIMUM: DEFAULT_MIN_VALUE,
        CONF_MAXIMUM: DEFAULT_MAX_VALUE,
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_MIN_SWITCH_TIME: DEFAULT_SWITCH_TIME,
        CONF_STEP: DEFAULT_STEP,
        CONF_MODE: DEFAULT_MODE,
    }

    assert result["options"] == expected_config
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == expected_config
    assert config_entry.title == "My slow_pwm"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize("platform", ("number",))
async def test_options(hass: HomeAssistant, platform: str) -> None:
    """Test reconfiguring."""
    outputs_1 = ["switch.output_1", "switch.output_2"]
    outputs_2 = ["switch.output_1", "switch.output_2", "switch.output_3"]

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={CONF_NAME: "My slow_pwm", CONF_OUTPUTS: outputs_1},
        title="My slow_pwm",
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, CONF_OUTPUTS) == outputs_1

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_OUTPUTS: outputs_2}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_OUTPUTS: outputs_2,
        CONF_NAME: "My slow_pwm",
        CONF_MINIMUM: DEFAULT_MIN_VALUE,
        CONF_MAXIMUM: DEFAULT_MAX_VALUE,
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_MIN_SWITCH_TIME: DEFAULT_SWITCH_TIME,
        CONF_STEP: DEFAULT_STEP,
        CONF_MODE: DEFAULT_MODE,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        CONF_OUTPUTS: outputs_2,
        CONF_NAME: "My slow_pwm",
        CONF_MINIMUM: DEFAULT_MIN_VALUE,
        CONF_MAXIMUM: DEFAULT_MAX_VALUE,
        CONF_CYCLE_TIME: DEFAULT_CYCLE_TIME,
        CONF_MIN_SWITCH_TIME: DEFAULT_SWITCH_TIME,
        CONF_STEP: DEFAULT_STEP,
        CONF_MODE: DEFAULT_MODE,
    }
    assert config_entry.title == "My slow_pwm"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get(f"{platform}.my_slow_pwm")
    assert state.state == "0.0"
