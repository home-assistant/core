"""Test the Legrand Home+ Control config options flow."""
from homeassistant import data_entry_flow
from homeassistant.components.homepluscontrol.const import DOMAIN

from tests.common import MockConfigEntry


async def test_config_options_flow(hass):
    """Test config options flow."""
    valid_option = {
        "plant_update_interval": "301",
        "plant_topology_update_interval": "302",
        "module_status_update_interval": "303",
    }

    expected_result = {
        "plant_update_interval": "301",
        "plant_topology_update_interval": "302",
        "module_status_update_interval": "303",
    }

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["options_listener_remover"] = "prevent_callback"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={},
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=valid_option
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    for k, v in expected_result.items():
        assert config_entry.options[k] == v


async def test_invalid_options_flow(hass):
    """Test config options flow with invalid input."""
    input_option = {
        "plant_update_interval": "7200",
        "plant_topology_update_interval": "3600",
        "module_status_update_interval": "300",
    }

    # Valid values are: 0 < int <= 86400
    invalid_values = [-1, "non-int", 0, 86401, 300000]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["options_listener_remover"] = "prevent_callback"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={},
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    for interval in input_option:
        for i_value in invalid_values:
            input_option[interval] = i_value

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=input_option
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        form_errors = result.get("errors", None)
        assert form_errors is not None
        assert form_errors.get(interval) == "invalid_update_interval"
