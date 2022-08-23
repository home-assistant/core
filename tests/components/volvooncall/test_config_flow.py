"""Test the Volvo On Call config flow."""
from unittest.mock import Mock, patch

from aiohttp import ClientResponseError

from homeassistant import config_entries
from homeassistant.components.volvooncall.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert len(result["errors"]) == 0

    with patch("volvooncall.Connection.get"), patch(
        "homeassistant.components.volvooncall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "region": "na",
                "mutable": True,
                "scandinavian_miles": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "region": "na",
        "mutable": True,
        "scandinavian_miles": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    exc = ClientResponseError(Mock(), (), status=401)

    with patch(
        "volvooncall.Connection.get",
        side_effect=exc,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "region": "na",
                "mutable": True,
                "scandinavian_miles": False,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_flow_already_configured(hass: HomeAssistant) -> None:
    """Test we handle a flow that has already been configured."""
    first_entry = MockConfigEntry(domain=DOMAIN, unique_id="test-username")
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert len(result["errors"]) == 0

    with patch("volvooncall.Connection.get"), patch(
        "homeassistant.components.volvooncall.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "region": "na",
                "mutable": True,
                "scandinavian_miles": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_other_exception(hass: HomeAssistant) -> None:
    """Test we handle other exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "volvooncall.Connection.get",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "region": "na",
                "mutable": True,
                "scandinavian_miles": False,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_import(hass: HomeAssistant) -> None:
    """Test a YAML import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == FlowResultType.FORM
    assert len(result["errors"]) == 0

    with patch("volvooncall.Connection.get"), patch(
        "homeassistant.components.volvooncall.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.volvooncall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "region": "na",
                "mutable": True,
                "scandinavian_miles": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "region": "na",
        "mutable": True,
        "scandinavian_miles": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1
