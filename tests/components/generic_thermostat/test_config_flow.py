"""Test the Generic Thermostat config flow."""
from unittest.mock import patch

from homeassistant.components.generic_thermostat.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    "name": "test_thermostat",
    "heater": "input_boolean.test",
    "target_sensor": "sensor.test",
}

FIXTURE_USER_INPUT_OPTIONS = {
    "min_temp": 10.2,
    "max_temp": 20.1,
    "target_temp": 15,
    "ac_mode": False,
    "min_cycle_duration": 5,
    "cold_tolerance": 0.5,
    "hot_tolerance": 0.5,
    "keep_alive": False,
    "initial_hvac_mode": "off",
    "precision": "0.1",
    "target_temp_step": 0.5,
}


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user initiated form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.generic_thermostat.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=FIXTURE_USER_INPUT
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=FIXTURE_USER_INPUT_OPTIONS,
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=FIXTURE_USER_INPUT_OPTIONS,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == FIXTURE_USER_INPUT_OPTIONS
