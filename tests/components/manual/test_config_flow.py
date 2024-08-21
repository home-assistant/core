"""Test the Worldclock config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.manual.const import (
    CONF_ARMING_STATES,
    CONF_CODE_ARM_REQUIRED,
    DEFAULT_ALARM_NAME,
    DEFAULT_ARMING_TIME,
    DEFAULT_DELAY_TIME,
    DEFAULT_DISARM_AFTER_TRIGGER,
    DEFAULT_TRIGGER_TIME,
    DOMAIN,
    SUPPORTED_ARMING_STATES,
)
from homeassistant.const import (
    CONF_ARMING_TIME,
    CONF_CODE,
    CONF_DELAY_TIME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_TRIGGER_TIME,
    STATE_ALARM_ARMED_AWAY,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_ALARM_NAME,
            CONF_CODE: "1234",
            CONF_CODE_ARM_REQUIRED: True,
            CONF_DELAY_TIME: {"seconds": DEFAULT_DELAY_TIME.total_seconds()},
            CONF_ARMING_TIME: {"seconds": DEFAULT_ARMING_TIME.total_seconds()},
            CONF_TRIGGER_TIME: {"seconds": DEFAULT_TRIGGER_TIME.total_seconds()},
            CONF_DISARM_AFTER_TRIGGER: DEFAULT_DISARM_AFTER_TRIGGER,
            CONF_ARMING_STATES: SUPPORTED_ARMING_STATES,
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "disarmed_trigger_time": {"seconds": 0},
            "armed_home_arming_time": {"seconds": 0},
            "armed_home_delay_time": {"seconds": 0},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_ALARM_NAME,
        CONF_CODE: "1234",
        CONF_CODE_ARM_REQUIRED: True,
        CONF_DELAY_TIME: {"seconds": 60},
        CONF_ARMING_TIME: {"seconds": 60},
        CONF_TRIGGER_TIME: {"seconds": 120},
        CONF_DISARM_AFTER_TRIGGER: DEFAULT_DISARM_AFTER_TRIGGER,
        CONF_ARMING_STATES: SUPPORTED_ARMING_STATES,
        "disarmed_trigger_time": {"seconds": 0},
        "armed_home_arming_time": {"seconds": 0},
        "armed_home_delay_time": {"seconds": 0},
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_schema_not_all_states(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form correctly with not all specific states."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_ALARM_NAME,
            CONF_CODE: "1234",
            CONF_CODE_ARM_REQUIRED: True,
            CONF_DELAY_TIME: {"seconds": DEFAULT_DELAY_TIME.total_seconds()},
            CONF_ARMING_TIME: {"seconds": DEFAULT_ARMING_TIME.total_seconds()},
            CONF_TRIGGER_TIME: {"seconds": DEFAULT_TRIGGER_TIME.total_seconds()},
            CONF_DISARM_AFTER_TRIGGER: DEFAULT_DISARM_AFTER_TRIGGER,
            CONF_ARMING_STATES: [STATE_ALARM_ARMED_AWAY],
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "disarmed_trigger_time": {"seconds": 0},
            "armed_away_arming_time": {"seconds": 0},
            "armed_away_delay_time": {"seconds": 0},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_ALARM_NAME,
        CONF_CODE: "1234",
        CONF_CODE_ARM_REQUIRED: True,
        CONF_DELAY_TIME: {"seconds": 60},
        CONF_ARMING_TIME: {"seconds": 60},
        CONF_TRIGGER_TIME: {"seconds": 120},
        CONF_DISARM_AFTER_TRIGGER: DEFAULT_DISARM_AFTER_TRIGGER,
        CONF_ARMING_STATES: [STATE_ALARM_ARMED_AWAY],
        "disarmed_trigger_time": {"seconds": 0},
        "armed_away_arming_time": {"seconds": 0},
        "armed_away_delay_time": {"seconds": 0},
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test options flow."""

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CODE: "4321",
            CONF_CODE_ARM_REQUIRED: True,
            CONF_DELAY_TIME: {"seconds": DEFAULT_DELAY_TIME.total_seconds()},
            CONF_ARMING_TIME: {"seconds": DEFAULT_ARMING_TIME.total_seconds()},
            CONF_TRIGGER_TIME: {"seconds": DEFAULT_TRIGGER_TIME.total_seconds()},
            CONF_DISARM_AFTER_TRIGGER: DEFAULT_DISARM_AFTER_TRIGGER,
            CONF_ARMING_STATES: SUPPORTED_ARMING_STATES,
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "disarmed_trigger_time": {"seconds": 0},
            "armed_home_arming_time": {"seconds": 0},
            "armed_home_delay_time": {"seconds": 0},
            "armed_away_delay_time": {"seconds": 120},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: DEFAULT_ALARM_NAME,
        CONF_CODE: "4321",
        CONF_CODE_ARM_REQUIRED: True,
        CONF_DELAY_TIME: {"seconds": 60},
        CONF_ARMING_TIME: {"seconds": 60},
        CONF_TRIGGER_TIME: {"seconds": 120},
        CONF_DISARM_AFTER_TRIGGER: DEFAULT_DISARM_AFTER_TRIGGER,
        CONF_ARMING_STATES: SUPPORTED_ARMING_STATES,
        "disarmed_trigger_time": {"seconds": 0},
        "armed_home_arming_time": {"seconds": 0},
        "armed_home_delay_time": {"seconds": 0},
        "armed_away_delay_time": {"seconds": 120},
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    state = hass.states.get("alarm_control_panel.ha_alarm")
    assert state is not None
