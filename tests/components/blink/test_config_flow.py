"""Test the Blink config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.blink import DOMAIN

from tests.async_mock import Mock, patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.blink.config_flow.Blink",
        return_value=Mock(get_auth_token=Mock(return_value=True)),
    ), patch(
        "homeassistant.components.blink.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.blink.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.asaync_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "blink@example.com"
    assert result2["data"] == {
        "ussername": "blink@example.com",
        "password": "example",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
