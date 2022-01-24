"""Test the moehlenhoff_alpha2 config flow."""
import asyncio
from unittest.mock import patch

from homeassistant.components.moehlenhoff_alpha2.const import DOMAIN
from homeassistant.core import HomeAssistant


async def mock_fetch_static_data(self):
    """Mock moehlenhoff_alpha2.Alpha2Base._fetch_static_data."""
    self.static_data = {
        "Devices": {"Device": {"ID": "fake_id", "NAME": "fake_base_name"}}
    }


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    with patch(
        "moehlenhoff_alpha2.Alpha2Base._fetch_static_data", mock_fetch_static_data
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data={"host": "fake_host"}
        )
        assert result["title"] == "fake_base_name"
        assert result["type"] == "create_entry"
        assert not result["result"].unique_id

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data={"host": "fake_host"}
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""

    with patch(
        "moehlenhoff_alpha2.Alpha2Base._fetch_static_data", mock_fetch_static_data
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"host": "fake_host_user"}
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "fake_base_name"
        assert result["data"]["host"] == "fake_host_user"


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test connection error."""
    with patch(
        "moehlenhoff_alpha2.Alpha2Base._fetch_static_data",
        side_effect=asyncio.TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"host": "127.0.0.1"}
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"


async def test_unexpected_error(hass: HomeAssistant) -> None:
    """Test unexpected error."""

    with patch(
        "moehlenhoff_alpha2.Alpha2Base._fetch_static_data",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"host": "10.10.10.10"}
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "unknown"
