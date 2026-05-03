"""Test for compensation config flow."""

from unittest.mock import AsyncMock

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
