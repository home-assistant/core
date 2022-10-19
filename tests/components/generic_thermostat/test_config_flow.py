"""Tests for the Gneric Thermostat config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.generic_thermostat.consts import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DATA = {
    "name": "Generic Thermostat",
    "heater": "switch.doe",
    "target_sensor": "sensor.doe",
    "min_temp": 7,
    "max_temp": 35,
    "target_temp": 20.1,
    "ac_mode": True,
    "min_cycle_duration": "00:01:00",
    "cold_tolerance": 0.1,
    "hot_tolerance": 0.1,
    "keep_alive": "00:05:00",
    "initial_hvac_mode": "auto",
    "precision": 0.5,
    "target_temp_step": 0.5,
}


async def test_user(hass: HomeAssistant):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=MOCK_DATA,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["options"]["name"] == "Generic Thermostat"


async def test_import(hass: HomeAssistant):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_DATA,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["options"]["name"] == "Generic Thermostat"


async def test_form_already_configured(hass: HomeAssistant):
    """Test that an entry with unique id can only be added once."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{DOMAIN}.generic_thermostat",
        data=MOCK_DATA,
    ).add_to_hass(hass)

    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result_configure = await hass.config_entries.flow.async_configure(
        result_init["flow_id"],
        {
            "heater": "switch.doe",
            "target_sensor": "sensor.doe",
        },
    )
    await hass.async_block_till_done()

    assert result_configure["type"] == data_entry_flow.FlowResultType.ABORT
    assert result_configure["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{DOMAIN}.generic_thermostat",
        data={},
        options=MOCK_DATA,
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "heater": "switch.doe",
            "target_sensor": "sensor.doe",
            "target_temp": 5,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["target_temp"] == 5.0
