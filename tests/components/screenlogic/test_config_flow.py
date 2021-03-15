"""Test the Pentair ScreenLogic config flow."""
from unittest.mock import patch

from screenlogicpy import ScreenLogicError

from homeassistant import config_entries, setup
from homeassistant.components.screenlogic.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.screenlogic.config_flow.async_get_mac_address",
        return_value="00-C0-33-01-01-01",
    ), patch(
        "homeassistant.components.screenlogic.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.screenlogic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_PORT: 80,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Pentair: 01-01-01"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_PORT: 80,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.screenlogic.config_flow.async_get_mac_address",
        side_effect=ScreenLogicError("Unknown socket error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_PORT: 80,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}
