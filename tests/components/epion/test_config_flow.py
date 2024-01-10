"""Tests for the Epion config flow."""
from unittest.mock import Mock, patch

from epion import EpionAuthenticationError, EpionConnectionError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.epion.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

API_KEY = "test-key-123"


@pytest.fixture(name="epion_api")
def mock_controller():
    """Mock the Epion API."""
    api = Mock()
    with patch("epion.Epion", return_value=api):
        yield api


async def test_user_flow(hass: HomeAssistant, epion_api: Mock) -> None:
    """Test various error during user initiated flow."""

    # Test with inactive / deactivated account
    epion_api.get_current.return_value = {"devices": []}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_KEY: API_KEY},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_auth"}

    # Test with invalid auth
    epion_api.get_current.side_effect = EpionAuthenticationError("Invalid API key")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_KEY: API_KEY},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_auth"}

    # Test with connection timeout
    epion_api.get_current.side_effect = EpionConnectionError("Timeout problem")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_KEY: API_KEY},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}

    # Test with valid data
    epion_api.get_current.return_value = {
        "devices": [{"deviceId": "abc", "deviceName": "Test Device"}]
    }
    epion_api.get_current.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_KEY: API_KEY},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY

    data = result.get("data")
    assert data
    assert data[CONF_API_KEY] == API_KEY
