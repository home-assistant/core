"""Test the SRP Energy config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.srp_energy.const import CONF_IS_TOU, SRP_ENERGY_DOMAIN

from . import ENTRY_CONFIG, init_integration


async def test_form(hass):
    """Test user config."""
    # First get the form
    result = await hass.config_entries.flow.async_init(
        SRP_ENERGY_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Fill submit form data for config entry
    with patch(
        "homeassistant.components.srp_energy.config_flow.SrpEnergyClient"
    ), patch(
        "homeassistant.components.srp_energy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG,
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "Test"
        assert result["data"][CONF_IS_TOU] is False

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test user config with invalid auth."""
    result = await hass.config_entries.flow.async_init(
        SRP_ENERGY_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.srp_energy.config_flow.SrpEnergyClient.validate",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG,
        )

        assert result["errors"]["base"] == "invalid_auth"


async def test_form_value_error(hass):
    """Test user config that throws a value error."""
    result = await hass.config_entries.flow.async_init(
        SRP_ENERGY_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.srp_energy.config_flow.SrpEnergyClient",
        side_effect=ValueError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG,
        )

        assert result["errors"]["base"] == "invalid_account"


async def test_form_unknown_exception(hass):
    """Test user config that throws an unknown exception."""
    result = await hass.config_entries.flow.async_init(
        SRP_ENERGY_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.srp_energy.config_flow.SrpEnergyClient",
        side_effect=Exception(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG,
        )

        assert result["errors"]["base"] == "unknown"


async def test_config(hass):
    """Test handling of configuration imported."""
    with patch("homeassistant.components.srp_energy.config_flow.SrpEnergyClient"):
        result = await hass.config_entries.flow.async_init(
            SRP_ENERGY_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=ENTRY_CONFIG,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_integration_already_configured(hass):
    """Test integration is already configured."""
    await init_integration(hass)
    result = await hass.config_entries.flow.async_init(
        SRP_ENERGY_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"
