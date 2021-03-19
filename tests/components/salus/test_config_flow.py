"""Test the NuHeat config flow."""
from unittest.mock import MagicMock, patch

import requests

from homeassistant import config_entries
from homeassistant.components.salus.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_PASSWORD, CONF_USERNAME

from .mocks import MOCK_DEVICE_ID, MOCK_DEVICE_NAME, _get_mock_salus


async def test_form_user(hass):
    """Test we get the form with user source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.salus.config_flow.Api",
        return_value=_get_mock_salus(),
    ), patch(
        "homeassistant.components.salus.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.salus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == "form"
        assert result2["errors"] == {}
        assert result2["step_id"] == "device"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_DEVICE: MOCK_DEVICE_NAME,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_DEVICE: MOCK_DEVICE_ID,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.salus.config_flow.Api.login",
        side_effect=requests.ConnectTimeout(MagicMock(), MagicMock()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.salus.config_flow.Api.login",
        side_effect=Exception("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error_abort(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.salus.config_flow.Api.login",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "unknown"
