"""Test the oocsi config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.oocsi.config_flow import OOCSIDisconnect
from homeassistant.components.oocsi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

DATA = {CONF_NAME: "iddi", CONF_HOST: "192.168.0.0", CONF_PORT: 4444}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.oocsi.config_flow.OOCSI.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.oocsi.config_flow.OOCSI.stop",
        return_value=True,
    ), patch(
        "homeassistant.components.oocsi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "iddi"
    assert result2["data"] == DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.oocsi.config_flow.OOCSI.__init__",
        side_effect=OOCSIDisconnect("OOCSI has not been found"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}
