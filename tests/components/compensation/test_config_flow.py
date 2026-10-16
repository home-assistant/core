"""Test for compensation config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.compensation.const import (
    CONF_COMPENSATED_VALUE,
    CONF_DATAPOINTS,
    CONF_DEGREE,
    CONF_LOWER_LIMIT,
    CONF_POLYNOMIAL_CONFIG,
    CONF_PRECISION,
    CONF_UNCOMPENSATED_VALUE,
    CONF_UPPER_LIMIT,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: DEFAULT_NAME, CONF_ENTITY_ID: "sensor.test_sensor"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOWER_LIMIT: False,
            CONF_POLYNOMIAL_CONFIG: {
                CONF_DATAPOINTS: [
                    {CONF_COMPENSATED_VALUE: 6, CONF_UNCOMPENSATED_VALUE: 5},
                    {CONF_COMPENSATED_VALUE: 8, CONF_UNCOMPENSATED_VALUE: 7},
                ],
                CONF_DEGREE: 1,
            },
            CONF_PRECISION: 2,
            CONF_UPPER_LIMIT: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {}
    assert result["options"] == {
        CONF_ENTITY_ID: "sensor.test_sensor",
        CONF_LOWER_LIMIT: False,
        CONF_NAME: "Compensation",
        CONF_POLYNOMIAL_CONFIG: {
            CONF_DATAPOINTS: [
                {CONF_COMPENSATED_VALUE: 6, CONF_UNCOMPENSATED_VALUE: 5},
                {CONF_COMPENSATED_VALUE: 8, CONF_UNCOMPENSATED_VALUE: 7},
            ],
            CONF_DEGREE: 1,
        },
        CONF_PRECISION: 2,
        CONF_UPPER_LIMIT: False,
    }


@pytest.mark.parametrize(
    ("data_points", "error"),
    [
        pytest.param([], "not_enough_datapoints", id="no_datapoints"),
        pytest.param(
            [{CONF_COMPENSATED_VALUE: 6, CONF_UNCOMPENSATED_VALUE: 5}],
            "not_enough_datapoints",
            id="not_enough_datapoints",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant, data_points: list[dict[str, Any]], error: str
) -> None:
    """Test the flow shows an error for invalid data points and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: DEFAULT_NAME, CONF_ENTITY_ID: "sensor.test_sensor"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_POLYNOMIAL_CONFIG: {CONF_DATAPOINTS: data_points, CONF_DEGREE: 1},
            CONF_PRECISION: 2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_POLYNOMIAL_CONFIG: {
                CONF_DATAPOINTS: [
                    {CONF_COMPENSATED_VALUE: 6, CONF_UNCOMPENSATED_VALUE: 5},
                    {CONF_COMPENSATED_VALUE: 8, CONF_UNCOMPENSATED_VALUE: 7},
                ],
                CONF_DEGREE: 1,
            },
            CONF_PRECISION: 2,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the options flow updates the entry and reloads it."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_POLYNOMIAL_CONFIG: {
                CONF_DATAPOINTS: [
                    {CONF_COMPENSATED_VALUE: 2, CONF_UNCOMPENSATED_VALUE: 1},
                    {CONF_COMPENSATED_VALUE: 4, CONF_UNCOMPENSATED_VALUE: 2},
                ],
                CONF_DEGREE: 1,
            },
            CONF_PRECISION: 1,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_ENTITY_ID: "sensor.uncompensated",
        CONF_LOWER_LIMIT: False,
        CONF_NAME: "My compensation",
        CONF_POLYNOMIAL_CONFIG: {
            CONF_DATAPOINTS: [
                {CONF_COMPENSATED_VALUE: 2, CONF_UNCOMPENSATED_VALUE: 1},
                {CONF_COMPENSATED_VALUE: 4, CONF_UNCOMPENSATED_VALUE: 2},
            ],
            CONF_DEGREE: 1,
        },
        CONF_PRECISION: 1,
        CONF_UPPER_LIMIT: False,
    }

    hass.states.async_set("sensor.uncompensated", "5")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.my_compensation").state == "10.0"
