"""Test the Eight Sleep config flow."""
from homeassistant import config_entries
from homeassistant.components.eight_sleep.const import DOMAIN
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
    }


async def test_form_invalid_auth(hass, token_error) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "bad-username",
            "password": "bad-password",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import(hass) -> None:
    """Test import works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "username": "test-username",
            "password": "test-password",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        "username": "test-username",
        "password": "test-password",
    }


async def test_import_invalid_auth(hass, token_error) -> None:
    """Test we handle invalid auth on import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "username": "bad-username",
            "password": "bad-password",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
