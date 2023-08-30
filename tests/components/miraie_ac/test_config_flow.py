"""Test the MirAIe AC config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.miraie_ac.config_flow import (
    AuthException,
    ConnectionException,
    MobileNotRegisteredException,
    ValidationError,
)
from homeassistant.components.miraie_ac.const import CONFIG_KEY_USER_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.miraie_ac.config_flow.MirAIeAPI.initialize",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONFIG_KEY_USER_ID: "+919876543219", CONF_PASSWORD: "P@ssw0rD"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "MirAIe"
    assert result2["data"] == {
        CONFIG_KEY_USER_ID: "+919876543219",
        CONF_PASSWORD: "P@ssw0rD",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.miraie_ac.config_flow.MirAIeAPI.initialize",
        side_effect=AuthException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONFIG_KEY_USER_ID: "+919876543219", CONF_PASSWORD: "P@ssw0rD"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.miraie_ac.config_flow.MirAIeAPI.initialize",
        side_effect=ConnectionException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONFIG_KEY_USER_ID: "+919876543219", CONF_PASSWORD: "P@ssw0rD"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_mobile_not_registered(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.miraie_ac.config_flow.MirAIeAPI.initialize",
        side_effect=MobileNotRegisteredException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONFIG_KEY_USER_ID: "+919876543219", CONF_PASSWORD: "P@ssw0rD"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "mobile_not_registered"}


async def test_form_invalid_mobile(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.miraie_ac.config_flow.MirAIeAPI.initialize",
        side_effect=ValidationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONFIG_KEY_USER_ID: "+9198765432", CONF_PASSWORD: "P@ssw0rD"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_mobile"}


async def test_form_unhandled_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.miraie_ac.config_flow.MirAIeAPI.initialize",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONFIG_KEY_USER_ID: "+919876543219", CONF_PASSWORD: "P@ssw0rD"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
