"""Tests for Trinnov Altitude config flow."""

from unittest.mock import AsyncMock

from trinnov_altitude.exceptions import ConnectionFailedError, ConnectionTimeoutError

from homeassistant.components.trinnov_altitude.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_HOST

from tests.common import MockConfigEntry


async def test_user_config_flow(hass: HomeAssistant, mock_device: AsyncMock) -> None:
    """Test user config flow."""

    # Test connection failed
    #
    # Note: I could not get this test to pass when isolating in a separate test.
    # There appears to be a race condition with mocking that I could not resolve
    # despite other tests having the same pattern.

    mock_device.connect.side_effect = ConnectionFailedError("message")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "invalid_host"}

    # Test connection timeout

    mock_device.connect.side_effect = ConnectionTimeoutError("message")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Test success

    mock_device.connect.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == MOCK_HOST


async def test_user_config_flow_device_exists_abort(
    hass: HomeAssistant, mock_device: AsyncMock, mock_integration: MockConfigEntry
) -> None:
    """Test flow aborts when device already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: MOCK_HOST}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
