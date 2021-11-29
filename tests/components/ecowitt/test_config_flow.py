"""Test the Ecowitt config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.ecowitt.const import (
    CONF_UNIT_BARO,
    CONF_UNIT_LIGHTNING,
    CONF_UNIT_RAIN,
    CONF_UNIT_WIND,
    CONF_UNIT_WINDCHILL,
    DOMAIN,
    W_TYPE_HYBRID,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PORT, CONF_UNIT_SYSTEM_METRIC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from . import EcoWittListenerMock

from tests.common import MockConfigEntry

TEST_DATA = {CONF_PORT: 4199}
TEST_ECOWITT_ID = "fake_ecowitt"

TEST_OPTIONS = {
    CONF_UNIT_BARO: CONF_UNIT_SYSTEM_METRIC,
    CONF_UNIT_WIND: CONF_UNIT_SYSTEM_METRIC,
    CONF_UNIT_RAIN: CONF_UNIT_SYSTEM_METRIC,
    CONF_UNIT_WINDCHILL: W_TYPE_HYBRID,
    CONF_UNIT_LIGHTNING: CONF_UNIT_SYSTEM_METRIC,
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.ecowitt.EcoWittListener",
        new=EcoWittListenerMock,
    ), patch(
        "homeassistant.components.ecowitt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["step_id"] == "initial_options"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
    assert result3["data"] == TEST_DATA
    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test setting options using the options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ECOWITT_ID,
        data=TEST_DATA,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ecowitt.EcoWittListener",
        new=EcoWittListenerMock,
    ), patch(
        "homeassistant.components.ecowitt.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=TEST_OPTIONS,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == TEST_OPTIONS
