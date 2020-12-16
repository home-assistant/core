"""Test the Niu config flow."""
from niu import NiuAPIException, NiuNetException, NiuServerException

from homeassistant import config_entries, setup
from homeassistant.components.niu.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.niu.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    with patch("homeassistant.components.niu.config_flow.validate_input"), patch(
        "homeassistant.components.niu.config_flow.NiuCloud.connect", return_value=True
    ), patch(
        "homeassistant.components.niu.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.niu.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.niu.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.niu.config_flow.NiuCloud.connect",
        side_effect=NiuAPIException,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.niu.config_flow.NiuCloud.connect",
        side_effect=NiuServerException,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result4["type"] == "form"
    assert result4["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.niu.config_flow.NiuCloud.connect",
        return_value=None,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result4["type"] == "form"
    assert result4["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.niu.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.niu.config_flow.NiuCloud.connect",
        side_effect=NiuNetException,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_other_exception(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.niu.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
