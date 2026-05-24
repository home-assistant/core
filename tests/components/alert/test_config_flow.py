"""Test the Alert config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.alert.const import DOMAIN
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REPEAT,
    CONF_STATE,
    STATE_IDLE,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

WATCHED_ENTITY = "input_boolean.watched"


async def test_config_flow_create(hass: HomeAssistant) -> None:
    """A user can create an alert via the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.alert.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My alert",
                CONF_ENTITY_ID: WATCHED_ENTITY,
                CONF_STATE: STATE_ON,
                CONF_REPEAT: ["1", "5"],
                "can_acknowledge": True,
                "skip_first": False,
                "notifiers": [],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My alert"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_NAME: "My alert",
        CONF_ENTITY_ID: WATCHED_ENTITY,
        CONF_STATE: STATE_ON,
        CONF_REPEAT: [1.0, 5.0],
        "can_acknowledge": True,
        "skip_first": False,
        "notifiers": [],
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("repeat_input", "error"),
    [
        ([], "repeat_required"),
        (["not-a-number"], "invalid_repeat"),
        (["0.001"], "invalid_repeat"),
    ],
    ids=("empty", "non-numeric", "below-minimum"),
)
async def test_config_flow_invalid_repeat(
    hass: HomeAssistant, repeat_input: list[str], error: str
) -> None:
    """Invalid repeat values surface a form error rather than creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Bad alert",
            CONF_ENTITY_ID: WATCHED_ENTITY,
            CONF_STATE: STATE_ON,
            CONF_REPEAT: repeat_input,
            "can_acknowledge": True,
            "skip_first": False,
            "notifiers": [],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_entity_created_from_entry(hass: HomeAssistant) -> None:
    """An AlertEntity is added when a config entry is set up, and removed on unload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Alarm went off",
        data={},
        options={
            CONF_NAME: "Alarm went off",
            CONF_ENTITY_ID: WATCHED_ENTITY,
            CONF_STATE: STATE_ON,
            CONF_REPEAT: [1.0],
            "can_acknowledge": True,
            "skip_first": False,
            "notifiers": [],
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("alert.alarm_went_off")
    assert state is not None
    assert state.state == STATE_IDLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # Entity registry keeps the entry; the entity reports unavailable after unload.
    assert hass.states.get("alert.alarm_went_off").state == "unavailable"


async def test_options_flow_updates_entity(hass: HomeAssistant) -> None:
    """Editing options re-creates the entity with the new configuration."""
    other_entity = "input_boolean.other"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My alert",
        data={},
        options={
            CONF_NAME: "My alert",
            CONF_ENTITY_ID: WATCHED_ENTITY,
            CONF_STATE: STATE_ON,
            CONF_REPEAT: [1.0],
            "can_acknowledge": True,
            "skip_first": False,
            "notifiers": [],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ENTITY_ID: other_entity,
            CONF_STATE: "open",
            CONF_REPEAT: ["2"],
            "can_acknowledge": False,
            "skip_first": True,
            "notifiers": ["mobile"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options == {
        CONF_NAME: "My alert",
        CONF_ENTITY_ID: other_entity,
        CONF_STATE: "open",
        CONF_REPEAT: [2.0],
        "can_acknowledge": False,
        "skip_first": True,
        "notifiers": ["mobile"],
    }
    # Entity_id is still derived from the unchanged entry title
    state = hass.states.get("alert.my_alert")
    assert state is not None
    assert state.state == STATE_IDLE
