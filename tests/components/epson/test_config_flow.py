"""Test the epson config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.epson.config_flow import CannotConnect
from homeassistant.components.epson.const import DOMAIN

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
        "homeassistant.components.epson.config_flow.epson.Projector.get_property",
        return_value="04",
    ), patch(
        "homeassistant.components.epson.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.epson.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "name": "test-epson", "port": 80, "ssl": False},
        )
    print("res")
    print(result2)
    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-epson"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 80,
        "ssl": False,
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
        "homeassistant.components.epson.config_flow.epson.Projector.get_property",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "name": "test-epson", "port": 80, "ssl": False},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
