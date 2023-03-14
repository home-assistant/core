"""Test the Kostal Plenticore Solar Inverter config flow."""
import asyncio
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from pykoplenti import AuthenticationException

from homeassistant import config_entries
from homeassistant.components.kostal_plenticore.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_formx(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.kostal_plenticore.config_flow.ApiClient"
    ) as mock_api_class, patch(
        "homeassistant.components.kostal_plenticore.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        # mock of the context manager instance
        mock_api_ctx = MagicMock()
        mock_api_ctx.login = AsyncMock()
        mock_api_ctx.get_setting_values = AsyncMock(
            return_value={"scb:network": {"Hostname": "scb"}}
        )

        # mock of the return instance of ApiClient
        mock_api = MagicMock()
        mock_api.__aenter__.return_value = mock_api_ctx
        mock_api.__aexit__ = AsyncMock()

        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

        mock_api_class.assert_called_once_with(ANY, "1.1.1.1")
        mock_api.__aenter__.assert_called_once()
        mock_api.__aexit__.assert_called_once()
        mock_api_ctx.login.assert_called_once_with("test-password")
        mock_api_ctx.get_setting_values.assert_called_once()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "scb"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kostal_plenticore.config_flow.ApiClient"
    ) as mock_api_class:
        # mock of the context manager instance
        mock_api_ctx = MagicMock()
        mock_api_ctx.login = AsyncMock(
            side_effect=AuthenticationException(404, "invalid user"),
        )

        # mock of the return instance of ApiClient
        mock_api = MagicMock()
        mock_api.__aenter__.return_value = mock_api_ctx
        mock_api.__aexit__.return_value = None

        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"password": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kostal_plenticore.config_flow.ApiClient"
    ) as mock_api_class:
        # mock of the context manager instance
        mock_api_ctx = MagicMock()
        mock_api_ctx.login = AsyncMock(
            side_effect=asyncio.TimeoutError(),
        )

        # mock of the return instance of ApiClient
        mock_api = MagicMock()
        mock_api.__aenter__.return_value = mock_api_ctx
        mock_api.__aexit__.return_value = None

        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"host": "cannot_connect"}


async def test_form_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kostal_plenticore.config_flow.ApiClient"
    ) as mock_api_class:
        # mock of the context manager instance
        mock_api_ctx = MagicMock()
        mock_api_ctx.login = AsyncMock(
            side_effect=Exception(),
        )

        # mock of the return instance of ApiClient
        mock_api = MagicMock()
        mock_api.__aenter__.return_value = mock_api_ctx
        mock_api.__aexit__.return_value = None

        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test we handle already configured error."""
    MockConfigEntry(
        domain="kostal_plenticore",
        data={"host": "1.1.1.1", "password": "foobar"},
        unique_id="112233445566",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "password": "test-password",
        },
    )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
