"""Test the SRP Energy config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.srp_energy.const import CONF_IS_TOU, DOMAIN
from homeassistant.const import CONF_ID, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch


async def test_form(hass):
    """Test user config."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.srp_energy.config_flow.SrpEnergyClient"
    ), patch(
        "homeassistant.components.srp_energy.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.srp_energy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test",
                CONF_ID: "1",
                CONF_USERNAME: "abba",
                CONF_PASSWORD: "ana",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test"
    assert result2["data"] == {
        CONF_NAME: "Test",
        CONF_ID: "1",
        CONF_USERNAME: "abba",
        CONF_PASSWORD: "ana",
        CONF_IS_TOU: False,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
