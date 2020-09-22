"""Test the Govee LED strips config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.govee.config_flow import CannotConnect
from homeassistant.components.govee.const import DOMAIN, CONF_API_KEY, CONF_DELAY

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.govee.config_flow.Govee.get_devices",
        return_value=([], None),
    ), patch(
        "homeassistant.components.govee.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.govee.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api_key", CONF_DELAY: 7},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "govee"
    assert result2["data"] == {"api_key": "api_key", "delay": 7}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.govee.config_flow.Govee.get_devices",
        return_value=(None, "connection error")
        # side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api_key", CONF_DELAY: 7},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.govee.config_flow.Govee.get_devices",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api_key", CONF_DELAY: 7},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
