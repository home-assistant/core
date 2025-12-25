from unittest.mock import AsyncMock, patch

import pytest
from rotarex_api import InvalidAuth

from homeassistant import config_entries
from homeassistant.components.rotarex.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD


async def test_show_form(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_create_entry_success(hass):
    with patch(
        "homeassistant.components.rotarex.config_flow.RotarexApi"
    ) as mock_api:
        mock_api.return_value.login = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "password",
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "test@example.com"


async def test_invalid_auth(hass):
    with patch(
        "homeassistant.components.rotarex.config_flow.RotarexApi"
    ) as mock_api:
        mock_api.return_value.login = AsyncMock(
            side_effect=InvalidAuth
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "bad@example.com",
                CONF_PASSWORD: "wrong",
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass):
    with patch(
        "homeassistant.components.rotarex.config_flow.RotarexApi"
    ) as mock_api:
        mock_api.return_value.login = AsyncMock(
            side_effect=Exception
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "err@example.com",
                CONF_PASSWORD: "pw",
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
