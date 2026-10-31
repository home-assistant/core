"""Test for compensation config flow."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

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
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(lambda entry: entry.entity_id, id="entity_id"),
        pytest.param(lambda entry: entry.id, id="uuid"),
    ],
)
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    entity_registry: er.EntityRegistry,
    source: Callable[[er.RegistryEntry], str],
) -> None:
    """Test full flow."""
    source_entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique", suggested_object_id="test_sensor"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: DEFAULT_NAME, CONF_ENTITY_ID: source(source_entry)},
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
        pytest.param(
            [
                {CONF_COMPENSATED_VALUE: 1, CONF_UNCOMPENSATED_VALUE: 0},
                {CONF_COMPENSATED_VALUE: 1, CONF_UNCOMPENSATED_VALUE: 0},
            ],
            "invalid_datapoints",
            id="invalid_datapoints",
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
    hass.states.async_set("sensor.uncompensated", "5")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.my_compensation").state == "6.0"

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
            CONF_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            CONF_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
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
        CONF_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
        CONF_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        CONF_UPPER_LIMIT: False,
    }

    # The reloaded sensor picks up the existing source state without a new change
    state = hass.states.get("sensor.my_compensation")
    assert state.state == "10.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
