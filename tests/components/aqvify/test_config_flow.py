"""Test the Aqvify config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.aqvify.config_flow import ConnectError, HTTPError
from homeassistant.components.aqvify.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert bool(result["errors"]) is False

    with patch(
        "homeassistant.components.aqvify.config_flow.DevicesAPI.get_devices",
        return_value=[
            {"deviceKey": "AQ01337", "name": "AQ01337 Strandvägen"},
            {"deviceKey": "DEMO", "name": "Min brunn"},
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "https://test.aqvify.com",
                "api_key": "top-secret-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM

    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aqvify.config_flow.DevicesAPI.get_devices",
        side_effect=HTTPError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "https://test.aqvify.com",
                "api_key": "top-secret-api-key",
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
        "homeassistant.components.aqvify.config_flow.DevicesAPI.get_devices",
        side_effect=ConnectError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "https://test.aqvify.com",
                "api_key": "top-secret-api-key",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
