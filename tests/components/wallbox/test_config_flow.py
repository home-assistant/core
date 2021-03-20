"""Test the Wallbox config flow."""
from unittest.mock import patch, MagicMock

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.wallbox import config_flow
from homeassistant.components.wallbox.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.wallbox.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wallbox.config_flow.PlaceholderHub.authenticate",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wallbox.config_flow.PlaceholderHub.authenticate",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


def test_hub_class():
    """Test hub class."""

    station = ("12345",)
    username = ("test-username",)
    password = "test-password"

    hub = config_flow.PlaceholderHub(station, username, password)

    with patch(
        "homeassistant.components.wallbox.config_flow.Wallbox.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.wallbox.config_flow.Wallbox.getChargerStatus",
        return_value=True,
    ):
        assert hub.authenticate()
        assert hub.get_data()


async def test_validate_input(hass):
    data = {
        "station": "12345",
        "username": "test-username",
        "password": "test-password",
    }

    with patch(
        "homeassistant.components.wallbox.config_flow.Wallbox.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.wallbox.config_flow.Wallbox.getChargerStatus",
        return_value=True,
    ):

        result = await config_flow.validate_input(hass, data)

        assert result == {"title": "Wallbox Portal"}