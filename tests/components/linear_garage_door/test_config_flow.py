"""Test the Linear Garage Door config flow."""

from unittest.mock import patch

from linear_garage_door.errors import InvalidDeviceIDError, InvalidLoginError

from homeassistant import config_entries
from homeassistant.components.linear_garage_door.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .util import async_init_integration


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.linear_garage_door.config_flow.Linear.login",
        return_value=True,
    ), patch(
        "homeassistant.components.linear_garage_door.config_flow.Linear.get_sites",
        return_value=[{"id": "test-site-id", "name": "test-site-name"}],
    ), patch(
        "homeassistant.components.linear_garage_door.config_flow.Linear.close",
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


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauthentication."""

    entry = await async_init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "title_placeholders": {"name": entry.title},
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.linear_garage_door.config_flow.Linear.login",
        return_value=True,
    ), patch(
        "homeassistant.components.linear_garage_door.config_flow.Linear.get_sites",
        return_value=[{"id": "test-site-id", "name": "test-site-name"}],
    ), patch(
        "homeassistant.components.linear_garage_door.config_flow.Linear.close",
        return_value=None,
    ), patch(
        "uuid.uuid4", return_value="test-uuid"
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "new-email",
                "password": "new-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    entries = hass.config_entries.async_entries()
    assert len(entries) == 1
    assert entries[0].data == {
        "email": "new-email",
        "password": "new-password",
        "site_id": "test-site-id",
        "device_id": "test-uuid",
    }


async def test_form_invalid_login(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.linear_garage_door.config_flow.Linear.login",
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
        "homeassistant.components.linear_garage_door.config_flow.Linear.login",
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
        "homeassistant.components.linear_garage_door.config_flow.Linear.login",
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
