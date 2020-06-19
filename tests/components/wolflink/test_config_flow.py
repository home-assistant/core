"""Test the Wolf SmartSet Service config flow."""
from asynctest import patch
from httpcore._exceptions import ConnectError
from wolf_smartset.models import Device
from wolf_smartset.token_auth import InvalidAuth

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.wolflink.const import DOMAIN


async def test_show_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_device_step_form(hass):
    """Test we get the second step of config."""
    conf = {"username": "test-username", "password": "test-password"}

    with patch(
        "wolf_smartset.wolf_client.WolfClient.fetch_system_list",
        return_value=[Device(1234, 5678, "test-device")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device"


async def test_create_entry(hass):
    """Test entity creation from device step."""
    conf = {"username": "test-username", "password": "test-password"}
    device_name = "test-device"

    with patch(
        "wolf_smartset.wolf_client.WolfClient.fetch_system_list",
        return_value=[Device(1234, 5678, device_name)],
    ), patch("homeassistant.components.wolflink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )

        result_create_entry = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_name": device_name},
        )

    assert result_create_entry["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result_create_entry["title"] == device_name
    assert result_create_entry["data"] == {
        "username": conf["username"],
        "password": conf["password"],
        "device_name": device_name,
    }


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    conf = {"username": "test-username", "password": "test-password"}

    with patch(
        "wolf_smartset.wolf_client.WolfClient.fetch_system_list",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    conf = {"username": "test-username", "password": "test-password"}

    with patch(
        "wolf_smartset.wolf_client.WolfClient.fetch_system_list",
        side_effect=ConnectError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass):
    """Test we handle cannot connect error."""
    conf = {"username": "test-username", "password": "test-password"}

    with patch(
        "wolf_smartset.wolf_client.WolfClient.fetch_system_list", side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}
