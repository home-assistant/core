"""Test the Integration config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.integration.config_flow import InvalidSourceSensorError
from homeassistant.components.integration.const import (
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DOMAIN,
    TRAPEZOIDAL_METHOD,
)
from homeassistant.const import CONF_METHOD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

USER_INPUT = {
    CONF_SOURCE_SENSOR: "sensor.power",
    CONF_ROUND_DIGITS: 3,
    CONF_UNIT_PREFIX: "k",
    CONF_UNIT_TIME: "h",
    CONF_METHOD: TRAPEZOIDAL_METHOD,
}


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_show_config_from(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.integration.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == f"{USER_INPUT[CONF_SOURCE_SENSOR]} integral"
    assert result2["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_source(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.integration.config_flow.validate_input",
        side_effect=InvalidSourceSensorError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_source"}
