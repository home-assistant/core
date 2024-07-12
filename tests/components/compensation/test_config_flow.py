"""Test the Compensation config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.compensation.const import (
    CONF_DATAPOINTS,
    CONF_DEGREE,
    CONF_LOWER_LIMIT,
    CONF_PRECISION,
    CONF_UPPER_LIMIT,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_UNIT_OF_MEASUREMENT
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
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: "sensor.test_monitored",
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DATAPOINTS: [
                "1.0, 2.0",
                "2.0, 3.0",
            ],
            CONF_UPPER_LIMIT: False,
            CONF_LOWER_LIMIT: False,
            CONF_PRECISION: 2,
            CONF_DEGREE: 1,
            CONF_UNIT_OF_MEASUREMENT: "mm",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "sensor.test_monitored",
        CONF_DATAPOINTS: [
            "1.0, 2.0",
            "2.0, 3.0",
        ],
        CONF_UPPER_LIMIT: False,
        CONF_LOWER_LIMIT: False,
        CONF_PRECISION: 2,
        CONF_DEGREE: 1,
        CONF_UNIT_OF_MEASUREMENT: "mm",
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
            CONF_DATAPOINTS: [
                "1.0, 2.0",
                "2.0, 3.0",
            ],
            CONF_UPPER_LIMIT: False,
            CONF_LOWER_LIMIT: False,
            CONF_PRECISION: 2,
            CONF_DEGREE: 1,
            CONF_UNIT_OF_MEASUREMENT: "km",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "sensor.uncompensated",
        CONF_DATAPOINTS: [
            "1.0, 2.0",
            "2.0, 3.0",
        ],
        CONF_UPPER_LIMIT: False,
        CONF_LOWER_LIMIT: False,
        CONF_PRECISION: 2,
        CONF_DEGREE: 1,
        CONF_UNIT_OF_MEASUREMENT: "km",
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 2

    state = hass.states.get("sensor.compensation_sensor")
    assert state is not None


async def test_validation_options(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
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
            CONF_ENTITY_ID: "sensor.test_monitored",
        },
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DATAPOINTS: [
                "1.0, 2.0",
                "2.0, 3.0",
            ],
            CONF_UPPER_LIMIT: False,
            CONF_LOWER_LIMIT: False,
            CONF_PRECISION: 2,
            CONF_DEGREE: 2,
            CONF_UNIT_OF_MEASUREMENT: "km",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_enough_datapoints"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DATAPOINTS: [
                "1.0, 2.0",
                "2.0 3.0",
            ],
            CONF_UPPER_LIMIT: False,
            CONF_LOWER_LIMIT: False,
            CONF_PRECISION: 2,
            CONF_DEGREE: 1,
            CONF_UNIT_OF_MEASUREMENT: "km",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "incorrect_datapoints"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DATAPOINTS: [
                "1.0, 2.0",
                "2,0, 3.0",
            ],
            CONF_UPPER_LIMIT: False,
            CONF_LOWER_LIMIT: False,
            CONF_PRECISION: 2,
            CONF_DEGREE: 1,
            CONF_UNIT_OF_MEASUREMENT: "km",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "incorrect_datapoints"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DATAPOINTS: ["1.0, 2.0", "2.0, 3.0", "3.0, 4.0"],
            CONF_UPPER_LIMIT: False,
            CONF_LOWER_LIMIT: False,
            CONF_PRECISION: 2,
            CONF_DEGREE: 2,
            CONF_UNIT_OF_MEASUREMENT: "km",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "sensor.test_monitored",
        CONF_DATAPOINTS: ["1.0, 2.0", "2.0, 3.0", "3.0, 4.0"],
        CONF_UPPER_LIMIT: False,
        CONF_LOWER_LIMIT: False,
        CONF_PRECISION: 2,
        CONF_DEGREE: 2,
        CONF_UNIT_OF_MEASUREMENT: "km",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_entry_already_exist(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
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
            CONF_ENTITY_ID: "sensor.uncompensated",
        },
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DATAPOINTS: [
                "1.0, 2.0",
                "2.0, 3.0",
            ],
            CONF_UPPER_LIMIT: False,
            CONF_LOWER_LIMIT: False,
            CONF_PRECISION: 2,
            CONF_DEGREE: 1,
            CONF_UNIT_OF_MEASUREMENT: "mm",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
