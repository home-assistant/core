"""Test the History stats config flow."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time

from homeassistant import config_entries
from homeassistant.components.history_stats.const import (
    CONF_DURATION,
    CONF_END,
    CONF_START,
    CONF_TYPE_COUNT,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.components.recorder import Recorder
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_STATE, CONF_TYPE
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_form(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: "binary_sensor.test_monitored",
            CONF_TYPE: "count",
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATE: ["on"],
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
            CONF_END: "{{ utcnow() }}",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "binary_sensor.test_monitored",
        CONF_STATE: ["on"],
        CONF_TYPE: "count",
        CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
        CONF_END: "{{ utcnow() }}",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(
    recorder_mock: Recorder, hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test options flow."""

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_END: "{{ utcnow() }}",
            CONF_DURATION: {"hours": 8, "minutes": 0, "seconds": 0, "days": 20},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "binary_sensor.test_monitored",
        CONF_STATE: ["on"],
        CONF_TYPE: "count",
        CONF_END: "{{ utcnow() }}",
        CONF_DURATION: {"hours": 8, "minutes": 0, "seconds": 0, "days": 20},
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    state = hass.states.get("sensor.unnamed_statistics")
    assert state is not None


async def test_validation_options(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test validation."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: "binary_sensor.test_monitored",
            CONF_TYPE: "count",
        },
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "state"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATE: ["on"],
        },
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "options"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
            CONF_END: "{{ utcnow() }}",
            CONF_DURATION: {"hours": 8, "minutes": 0, "seconds": 0, "days": 20},
        },
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "options"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "only_two_keys_allowed"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
            CONF_END: "{{ utcnow() }}",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "binary_sensor.test_monitored",
        CONF_STATE: ["on"],
        CONF_TYPE: "count",
        CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
        CONF_END: "{{ utcnow() }}",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_entry_already_exist(
    recorder_mock: Recorder, hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test abort when entry already exist."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: "binary_sensor.test_monitored",
            CONF_TYPE: "count",
        },
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATE: ["on"],
        },
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
            CONF_END: "{{ utcnow() }}",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_config_flow_preview_success(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    # add state for the tests
    await hass.config.async_set_time_zone("UTC")
    utcnow = dt_util.utcnow()
    start_time = utcnow.replace(hour=0, minute=0, second=0, microsecond=0)
    t1 = start_time.replace(hour=3)
    t2 = start_time.replace(hour=4)
    t3 = start_time.replace(hour=5)

    monitored_entity = "binary_sensor.state"

    def _fake_states(*args, **kwargs):
        return {
            monitored_entity: [
                State(
                    monitored_entity,
                    "on",
                    last_changed=start_time,
                    last_updated=start_time,
                ),
                State(
                    monitored_entity,
                    "off",
                    last_changed=t1,
                    last_updated=t1,
                ),
                State(
                    monitored_entity,
                    "on",
                    last_changed=t2,
                    last_updated=t2,
                ),
            ]
        }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: monitored_entity,
            CONF_TYPE: CONF_TYPE_COUNT,
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATE: ["on"],
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "options"
    assert result["errors"] is None
    assert result["preview"] == "history_stats"

    with (
        patch(
            "homeassistant.components.recorder.history.state_changes_during_period",
            _fake_states,
        ),
        freeze_time(t3),
    ):
        await client.send_json_auto_id(
            {
                "type": "history_stats/start_preview",
                "flow_id": result["flow_id"],
                "flow_type": "config_flow",
                "user_input": {
                    CONF_ENTITY_ID: monitored_entity,
                    CONF_TYPE: CONF_TYPE_COUNT,
                    CONF_STATE: ["on"],
                    CONF_END: "{{now()}}",
                    CONF_START: "{{ today_at() }}",
                },
            }
        )
        msg = await client.receive_json()
        assert msg["success"]
        assert msg["result"] is None

        msg = await client.receive_json()
        assert msg["event"]["state"] == "2"


async def test_options_flow_preview(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the options flow preview."""
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
    client = await hass_ws_client(hass)

    # add state for the tests
    await hass.config.async_set_time_zone("UTC")
    utcnow = dt_util.utcnow()
    start_time = utcnow.replace(hour=0, minute=0, second=0, microsecond=0)
    t1 = start_time.replace(hour=3)
    t2 = start_time.replace(hour=4)
    t3 = start_time.replace(hour=5)

    monitored_entity = "binary_sensor.state"

    def _fake_states(*args, **kwargs):
        return {
            monitored_entity: [
                State(
                    monitored_entity,
                    "on",
                    last_changed=start_time,
                    last_updated=start_time,
                ),
                State(
                    monitored_entity,
                    "off",
                    last_changed=t1,
                    last_updated=t1,
                ),
                State(
                    monitored_entity,
                    "on",
                    last_changed=t2,
                    last_updated=t2,
                ),
                State(
                    monitored_entity,
                    "off",
                    last_changed=t2,
                    last_updated=t2,
                ),
            ]
        }

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: monitored_entity,
            CONF_TYPE: CONF_TYPE_COUNT,
            CONF_STATE: ["on"],
            CONF_END: "{{ now() }}",
            CONF_START: "{{ today_at() }}",
        },
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "history_stats"

    with (
        patch(
            "homeassistant.components.recorder.history.state_changes_during_period",
            _fake_states,
        ),
        freeze_time(t3),
    ):
        for end, exp_count in (
            ("{{now()}}", "2"),
            ("{{today_at('2:00')}}", "1"),
            ("{{today_at('23:00')}}", "2"),
        ):
            await client.send_json_auto_id(
                {
                    "type": "history_stats/start_preview",
                    "flow_id": result["flow_id"],
                    "flow_type": "options_flow",
                    "user_input": {
                        CONF_ENTITY_ID: monitored_entity,
                        CONF_TYPE: CONF_TYPE_COUNT,
                        CONF_STATE: ["on"],
                        CONF_END: end,
                        CONF_START: "{{ today_at() }}",
                    },
                }
            )

            msg = await client.receive_json()
            assert msg["success"]
            assert msg["result"] is None

            msg = await client.receive_json()
            assert msg["event"]["state"] == exp_count

        hass.states.async_set(monitored_entity, "on")

        msg = await client.receive_json()
        assert msg["event"]["state"] == "3"


async def test_options_flow_preview_errors(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the options flow preview."""
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
    client = await hass_ws_client(hass)

    # add state for the tests
    monitored_entity = "binary_sensor.state"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: monitored_entity,
            CONF_TYPE: CONF_TYPE_COUNT,
            CONF_STATE: ["on"],
            CONF_END: "{{ now() }}",
            CONF_START: "{{ today_at() }}",
        },
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "history_stats"

    for schema in (
        {CONF_END: "{{ now() }"},  # Missing '}' at end of template
        {CONF_START: "{{ today_at( }}"},  # Missing ')' in template function
        {CONF_DURATION: {"hours": 1}},  # Specified 3 period keys (1 too many)
        {CONF_START: ""},  # Specified 1 period keys (1 too few)
    ):
        await client.send_json_auto_id(
            {
                "type": "history_stats/start_preview",
                "flow_id": result["flow_id"],
                "flow_type": "options_flow",
                "user_input": {
                    CONF_ENTITY_ID: monitored_entity,
                    CONF_TYPE: CONF_TYPE_COUNT,
                    CONF_STATE: ["on"],
                    CONF_END: "{{ now() }}",
                    CONF_START: "{{ today_at() }}",
                    **schema,
                },
            }
        )

        msg = await client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "invalid_schema"

    for schema in (
        {CONF_END: "{{ nowwww() }}"},  # Unknown jinja function
        {CONF_START: "{{ today_at('abcde') }}"},  # Invalid value passed to today_at
        {CONF_END: '"{{ now() }}"'},  # Invalid quotes around template
    ):
        await client.send_json_auto_id(
            {
                "type": "history_stats/start_preview",
                "flow_id": result["flow_id"],
                "flow_type": "options_flow",
                "user_input": {
                    CONF_ENTITY_ID: monitored_entity,
                    CONF_TYPE: CONF_TYPE_COUNT,
                    CONF_STATE: ["on"],
                    CONF_END: "{{ now() }}",
                    CONF_START: "{{ today_at() }}",
                    **schema,
                },
            }
        )

        msg = await client.receive_json()
        assert msg["success"]
        assert msg["result"] is None

        msg = await client.receive_json()
        assert msg["event"]["error"]


async def test_options_flow_sensor_preview_config_entry_removed(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the option flow preview where the config entry is removed."""
    client = await hass_ws_client(hass)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: "sensor.test_monitored",
            CONF_TYPE: CONF_TYPE_COUNT,
            CONF_STATE: ["on"],
            CONF_START: "0",
            CONF_END: "1",
        },
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "history_stats"

    await hass.config_entries.async_remove(config_entry.entry_id)

    await client.send_json_auto_id(
        {
            "type": "history_stats/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                CONF_ENTITY_ID: "sensor.test_monitored",
                CONF_TYPE: CONF_TYPE_COUNT,
                CONF_STATE: ["on"],
                CONF_START: "0",
                CONF_END: "1",
            },
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "home_assistant_error",
        "message": "Config entry not found",
    }
