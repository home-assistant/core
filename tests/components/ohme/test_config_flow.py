"""Tests for the config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.ohme.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_session")
async def test_config_flow(hass: HomeAssistant) -> None:
    """Test config flow."""

    # Initial form load
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    # Failed login
    with patch("ohme.OhmeApiClient.async_refresh_session", return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "test@example.com", "password": "hunter1"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}

    # Successful login
    with patch("ohme.OhmeApiClient.async_refresh_session", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "test@example.com", "password": "hunter2"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
