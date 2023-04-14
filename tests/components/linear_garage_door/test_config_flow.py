"""Test the Linear Garage Door config flow."""

from unittest.mock import patch

from linear_garage_door.errors import InvalidDeviceIDError, InvalidLoginError

from homeassistant import config_entries
from homeassistant.components.linear_garage_door.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "linear_garage_door.Linear.login",
        return_value=True,
    ), patch(
        "linear_garage_door.Linear.get_sites",
        return_value=[{"id": "test-site-id", "name": "test-site-name"}],
    ), patch(
        "linear_garage_door.Linear.close",
        return_value=None,
    ), patch(
        "uuid.uuid4", return_value="test-uuid"
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "test-email",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.linear_garage_door.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"site": "test-site-id"}
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "test-site-name"
    assert result3["data"] == {
        "email": "test-email",
        "password": "test-password",
        "site_id": "test-site-id",
        "device_id": "test-uuid",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_login(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "linear_garage_door.Linear.login",
        side_effect=InvalidLoginError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "test-email",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_device_id(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )

    with patch(
        "linear_garage_door.Linear.login",
        side_effect=InvalidDeviceIDError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "test-email",
                "password": "test-password",
                "device_id": "invalid-device-id",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_device_id"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "linear_garage_door.Linear.login",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "test-email",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
