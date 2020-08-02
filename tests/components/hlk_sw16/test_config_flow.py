"""Test the Hi-Link HLK-SW16 config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.hlk_sw16.config_flow import (
    AlreadyConfigured,
    CannotConnect,
)
from homeassistant.components.hlk_sw16.const import DOMAIN

from tests.async_mock import patch

hlk_sw16_test_config = {
    "host": "1.1.1.1",
    "port": 8080,
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.validate_input",
        return_value=True,
    ), patch(
        "homeassistant.components.hlk_sw16.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.hlk_sw16.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], hlk_sw16_test_config,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.1.1.1:8080"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 8080,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.validate_input",
        side_effect=AlreadyConfigured,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], hlk_sw16_test_config,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "already_configured"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hlk_sw16.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], hlk_sw16_test_config,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
