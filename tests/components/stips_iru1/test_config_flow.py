"""Config flow tests for stips_iru1."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.stips_iru1.const import DOMAIN


async def test_form_shows(hass):
    """Test initial config flow form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_create_entry_success(hass):
    """Test config flow creates entry on successful auth and catalog fetch."""
    user_input = {
        "api_host": "stips.api.stagging.visionalization.net",
        "username": "demo",
        "password": "secret",
    }

    with (
        patch(
            "homeassistant.components.stips_iru1.config_flow.StipsApiClient.login",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.stips_iru1.config_flow.StipsApiClient.get_areas",
            new=AsyncMock(return_value=[{"id": 1, "name": "Home"}]),
        ),
        patch(
            "homeassistant.components.stips_iru1.config_flow.async_fetch_catalog_devices",
            new=AsyncMock(return_value=([], [{"uniqueName": "stips-iru1-123456"}])),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "STIPS (demo)"
