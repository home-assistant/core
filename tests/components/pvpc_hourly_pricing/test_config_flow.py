"""Tests for the pvpc_hourly_pricing config_flow."""
from homeassistant import data_entry_flow
from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.const import CONF_NAME

from . import check_valid_state


async def test_config_flow(hass):
    """
    Test config flow for pvpc_hourly_pricing.

    - Create a new entry with tariff "normal"
    - Check state and attributes
    - Use Options flow to change to tariff "coche_electrico"
    - Check new tariff state and compare both.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "test", ATTR_TARIFF: "normal"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    check_valid_state(state, tariff="normal")

    # get entry and min_price with tariff 'normal' to play with options flow
    entry = result["result"]
    min_price_normal_tariff = state.attributes["min price"]

    # Use options to change tariff
    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={ATTR_TARIFF: "coche_electrico"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][ATTR_TARIFF] == "coche_electrico"

    # check tariff change
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    check_valid_state(state, tariff="coche_electrico")

    # Check parsing was ok by ensuring that EV is better tariff than default one
    min_price_electric_car_tariff = state.attributes["min price"]
    assert min_price_electric_car_tariff < min_price_normal_tariff

    # Check abort when configuring another with same name
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "test", ATTR_TARIFF: "normal"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
