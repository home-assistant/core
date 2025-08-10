"""Test the Filter config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.filter.const import (
    CONF_FILTER_LOWER_BOUND,
    CONF_FILTER_NAME,
    CONF_FILTER_PRECISION,
    CONF_FILTER_RADIUS,
    CONF_FILTER_TIME_CONSTANT,
    CONF_FILTER_UPPER_BOUND,
    CONF_FILTER_WINDOW_SIZE,
    CONF_TIME_SMA_TYPE,
    DEFAULT_FILTER_RADIUS,
    DEFAULT_NAME,
    DEFAULT_PRECISION,
    DEFAULT_WINDOW_SIZE,
    DOMAIN,
    FILTER_NAME_LOWPASS,
    FILTER_NAME_OUTLIER,
    FILTER_NAME_RANGE,
    FILTER_NAME_THROTTLE,
    FILTER_NAME_TIME_SMA,
    FILTER_NAME_TIME_THROTTLE,
    TIME_SMA_LAST,
)
from homeassistant.components.recorder import Recorder
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entry_config", "options", "result_options"),
    [
        (
            {CONF_FILTER_NAME: FILTER_NAME_OUTLIER},
            {
                CONF_FILTER_WINDOW_SIZE: 1.0,
                CONF_FILTER_RADIUS: 2.0,
            },
            {
                CONF_FILTER_NAME: FILTER_NAME_OUTLIER,
                CONF_FILTER_WINDOW_SIZE: 1,
                CONF_FILTER_RADIUS: 2.0,
            },
        ),
        (
            {CONF_FILTER_NAME: FILTER_NAME_LOWPASS},
            {
                CONF_FILTER_WINDOW_SIZE: 1.0,
                CONF_FILTER_TIME_CONSTANT: 10.0,
            },
            {
                CONF_FILTER_NAME: FILTER_NAME_LOWPASS,
                CONF_FILTER_WINDOW_SIZE: 1,
                CONF_FILTER_TIME_CONSTANT: 10,
            },
        ),
        (
            {CONF_FILTER_NAME: FILTER_NAME_RANGE},
            {
                CONF_FILTER_LOWER_BOUND: 1.0,
                CONF_FILTER_UPPER_BOUND: 10.0,
            },
            {
                CONF_FILTER_NAME: FILTER_NAME_RANGE,
                CONF_FILTER_LOWER_BOUND: 1.0,
                CONF_FILTER_UPPER_BOUND: 10.0,
            },
        ),
        (
            {CONF_FILTER_NAME: FILTER_NAME_TIME_SMA},
            {
                CONF_TIME_SMA_TYPE: TIME_SMA_LAST,
                CONF_FILTER_WINDOW_SIZE: {"hours": 40, "minutes": 5, "seconds": 5},
            },
            {
                CONF_FILTER_NAME: FILTER_NAME_TIME_SMA,
                CONF_TIME_SMA_TYPE: TIME_SMA_LAST,
                CONF_FILTER_WINDOW_SIZE: {"hours": 40, "minutes": 5, "seconds": 5},
            },
        ),
        (
            {CONF_FILTER_NAME: FILTER_NAME_THROTTLE},
            {
                CONF_FILTER_WINDOW_SIZE: 1.0,
            },
            {
                CONF_FILTER_NAME: FILTER_NAME_THROTTLE,
                CONF_FILTER_WINDOW_SIZE: 1,
            },
        ),
        (
            {CONF_FILTER_NAME: FILTER_NAME_TIME_THROTTLE},
            {
                CONF_FILTER_WINDOW_SIZE: {"hours": 40, "minutes": 5, "seconds": 5},
            },
            {
                CONF_FILTER_NAME: FILTER_NAME_TIME_THROTTLE,
                CONF_FILTER_WINDOW_SIZE: {"hours": 40, "minutes": 5, "seconds": 5},
            },
        ),
    ],
)
async def test_form(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    entry_config: dict[str, Any],
    options: dict[str, Any],
    result_options: dict[str, Any],
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
            CONF_ENTITY_ID: "sensor.test_monitored",
            **entry_config,
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FILTER_PRECISION: DEFAULT_PRECISION, **options},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "sensor.test_monitored",
        CONF_FILTER_PRECISION: DEFAULT_PRECISION,
        **result_options,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(
    recorder_mock: Recorder, hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test options flow."""

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "outlier"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_FILTER_WINDOW_SIZE: 2.0,
            CONF_FILTER_RADIUS: 3.0,
            CONF_FILTER_PRECISION: DEFAULT_PRECISION,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "sensor.test_monitored",
        CONF_FILTER_NAME: FILTER_NAME_OUTLIER,
        CONF_FILTER_WINDOW_SIZE: 2,
        CONF_FILTER_RADIUS: 3.0,
        CONF_FILTER_PRECISION: DEFAULT_PRECISION,
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 2

    state = hass.states.get("sensor.filtered_sensor")
    assert state is not None


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
            CONF_ENTITY_ID: "sensor.test_monitored",
            CONF_FILTER_NAME: FILTER_NAME_OUTLIER,
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FILTER_WINDOW_SIZE: DEFAULT_WINDOW_SIZE,
            CONF_FILTER_RADIUS: DEFAULT_FILTER_RADIUS,
            CONF_FILTER_PRECISION: DEFAULT_PRECISION,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
