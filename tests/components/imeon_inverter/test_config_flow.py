"""Test the Imeon Inverter config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.imeon_inverter.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_SERIAL, TEST_USER_INPUT

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_login_async_setup_entry: Generator[AsyncMock]
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_USER_INPUT[CONF_ADDRESS]
    assert result2["data"] == TEST_USER_INPUT
    assert mock_login_async_setup_entry.call_count == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_timeout(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
        side_effect=ValueError("Host invalid"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_host"}


async def test_form_invalid_route(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
        side_effect=ValueError("Route invalid"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_route"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_manual_setup_already_exists(
    hass: HomeAssistant, mock_login_async_setup_entry: Generator[AsyncMock]
) -> None:
    """Test that a flow with an existing host aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIAL,
        data=TEST_USER_INPUT,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.get_serial",
            return_value=TEST_SERIAL,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
