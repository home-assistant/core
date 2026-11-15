"""Test the manual alarm control panel config flow."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.components.manual.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

ENTITY_ID = "alarm_control_panel.my_alarm"

DEFAULT_OPTIONS = {
    "code_arm_required": True,
    "arming_states": [
        "armed_away",
        "armed_home",
        "armed_night",
        "armed_vacation",
        "armed_custom_bypass",
    ],
    "arming_time": {"seconds": 60},
    "delay_time": {"seconds": 60},
    "trigger_time": {"seconds": 120},
    "disarm_after_trigger": False,
}


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow with default values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.manual.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "My alarm", "code": "1234"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My alarm"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My alarm",
        "code": "1234",
        **DEFAULT_OPTIONS,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_code_and_code_template(hass: HomeAssistant) -> None:
    """Test setting both a code and a code template shows an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "My alarm", "code": "1234", "code_template": "{{ '1234' }}"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "code_and_code_template"}

    with patch(
        "homeassistant.components.manual.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My alarm",
                "code_template": "{{ '1234' }}",
                "armed_away": {"arming_time": {"seconds": 5}},
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        "name": "My alarm",
        "code_template": "{{ '1234' }}",
        "armed_away": {"arming_time": {"seconds": 5}},
        **DEFAULT_OPTIONS,
    }


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow updates the entity."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={"name": "My alarm", **DEFAULT_OPTIONS},
        title="My alarm",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["code_format"] is None

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            **DEFAULT_OPTIONS,
            "code": "1234",
            "arming_states": ["armed_away"],
            "arming_time": {"seconds": 0},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "name": "My alarm",
        **DEFAULT_OPTIONS,
        "code": "1234",
        "arming_states": ["armed_away"],
        "arming_time": {"seconds": 0},
    }

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["code_format"] == "number"
    assert state.attributes["supported_features"] == (
        AlarmControlPanelEntityFeature.TRIGGER | AlarmControlPanelEntityFeature.ARM_AWAY
    )
