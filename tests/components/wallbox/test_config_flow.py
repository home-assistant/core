"""Test the Wallbox config flow."""
from unittest.mock import patch

from voluptuous.schema_builder import raises

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.wallbox import CannotConnect, InvalidAuth, config_flow
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
        "homeassistant.components.wallbox.config_flow.WallboxHub.async_authenticate",
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
        "homeassistant.components.wallbox.config_flow.WallboxHub.async_authenticate",
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
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_validate_input(hass):
    """Test we can validate input."""
    data = {
        "station": "12345",
        "username": "test-username",
        "password": "test-password",
    }

    def alternate_authenticate_method():
        return None

    def alternate_get_charger_status_method(station):
        data = '{"Temperature": 100, "Location": "Toronto", "Datetime": "2020-07-23", "Units": "Celsius"}'
        return data

    with patch(
        "wallbox.Wallbox.authenticate",
        side_effect=alternate_authenticate_method,
    ), patch(
        "wallbox.Wallbox.getChargerStatus",
        side_effect=alternate_get_charger_status_method,
    ):

        result = await config_flow.validate_input(hass, data)

        assert result == {"title": "Wallbox Portal"}


async def test_configflow_class():
    """Test configFlow class."""
    configflow = config_flow.ConfigFlow()
    assert configflow

    with patch(
        "homeassistant.components.wallbox.config_flow.validate_input",
        side_effect=TypeError,
    ), raises(Exception):
        assert await configflow.async_step_user(True)

    with patch(
        "homeassistant.components.wallbox.config_flow.validate_input",
        side_effect=CannotConnect,
    ), raises(Exception):
        assert await configflow.async_step_user(True)

    with patch(
        "homeassistant.components.wallbox.config_flow.validate_input",
    ), raises(Exception):
        assert await configflow.async_step_user(True)


def test_cannot_connect_class():
    """Test cannot Connect class."""
    cannot_connect = CannotConnect
    assert cannot_connect


def test_invalid_auth_class():
    """Test invalid auth class."""
    invalid_auth = InvalidAuth
    assert invalid_auth
