"""Test the OpenRGB config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.openrgb.config_flow import CannotConnect
from homeassistant.components.openrgb.const import DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    print(result)
    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBFlowHandler._try_connect",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.openrgb.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.openrgb.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 12345, CONF_CLIENT_ID: "test-client-id"},
        )
    print(result2)
    assert result2["type"] == "create_entry"
    assert result2["title"] == "openrgb"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 12345,
        "client_id": "test-client-id",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBFlowHandler._try_connect",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "port": 12345, "client_id": "test-client-id"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
