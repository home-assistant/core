"""Test the Trend config flow."""
import pytest
from voluptuous.error import MultipleInvalid

from homeassistant import data_entry_flow
from homeassistant.components.trend.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant


async def test_flow_fails_missing_data(hass: HomeAssistant) -> None:
    """Test the config flow doesn't allow missing data."""
    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Try configure with no fields. This should be an exception
    with pytest.raises(MultipleInvalid):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    # Clean up
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()


async def test_flow_succeeds_with_minimum_data(hass: HomeAssistant) -> None:
    """Test the config flow runs with necessary data."""
    user_input = {CONF_NAME: "Trend Sensor", CONF_ENTITY_ID: "sensor.test_sensor"}

    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Try configure with required fields
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
