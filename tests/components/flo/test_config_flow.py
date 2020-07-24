"""Test the flo config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.flo.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass, aioclient_mock_fixture):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flo.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.flo.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Home"
    assert result2["data"] == {"username": "test-username", "password": "test-password"}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass, aioclient_mock):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test-username", "password": "test-password"}
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
