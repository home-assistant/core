"""Test the Arctic Spa config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.arcticspa.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.arcticspa.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.components.arcticspa import CONF_API_KEY_VALUE

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.arcticspa.config_flow.Device.authenticate",
        return_value=200,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Arctic Spa Hot Tub API Key",
                "api_key": CONF_API_KEY_VALUE,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Arctic Spa Hot Tub API Key"
    assert result2["data"] == {
        "name": "Arctic Spa Hot Tub API Key",
        "api_key": CONF_API_KEY_VALUE,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.arcticspa.config_flow.Device.authenticate",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Arctic Spa Hot Tub API Key",
                "api_key": CONF_API_KEY_VALUE,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.arcticspa.config_flow.Device.authenticate",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Arctic Spa Hot Tub API Key",
                "api_key": "fake_api_key",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
