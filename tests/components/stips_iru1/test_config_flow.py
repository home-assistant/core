"""Config flow tests for stips_iru1."""

from unittest.mock import AsyncMock, patch

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.stips_iru1.api import (
    StipsApiAuthError,
    StipsApiError,
    StipsApiPermissionError,
)
from homeassistant.components.stips_iru1.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_form_shows(hass: HomeAssistant) -> None:
    """Test initial config flow form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert isinstance(result["data_schema"], vol.Schema)


async def test_create_entry_success(hass: HomeAssistant) -> None:
    """Test config flow creates entry on successful auth and catalog fetch."""
    user_input = {
        "api_host": "stips.api.staging.visionalization.net",
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


async def test_permission_error(hass: HomeAssistant) -> None:
    """Test permission error is handled."""
    user_input = {
        "api_host": "stips.api.staging.visionalization.net",
        "username": "demo",
        "password": "secret",
    }

    with patch(
        "homeassistant.components.stips_iru1.config_flow.StipsApiClient.login",
        new=AsyncMock(side_effect=StipsApiPermissionError()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "no_catalog_permission"


async def test_no_areas_error(hass: HomeAssistant) -> None:
    """Test no areas response is handled."""
    user_input = {
        "api_host": "stips.api.staging.visionalization.net",
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
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "no_areas"


async def test_catalog_fetch_error(hass: HomeAssistant) -> None:
    """Test catalog fetch errors are surfaced as connection issues."""
    user_input = {
        "api_host": "stips.api.staging.visionalization.net",
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
            new=AsyncMock(side_effect=StipsApiError()),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test unexpected type/value errors are handled."""
    user_input = {
        "api_host": "stips.api.staging.visionalization.net",
        "username": "demo",
        "password": "secret",
    }

    with patch(
        "homeassistant.components.stips_iru1.config_flow.StipsApiClient.login",
        new=AsyncMock(side_effect=TypeError()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "unknown"


async def test_auth_error(hass: HomeAssistant) -> None:
    """Test auth error is handled."""
    user_input = {
        "api_host": "stips.api.staging.visionalization.net",
        "username": "bad",
        "password": "wrong",
    }

    with patch(
        "homeassistant.components.stips_iru1.config_flow.StipsApiClient.login",
        new=AsyncMock(side_effect=StipsApiAuthError()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == "form"


async def test_no_devices_error(hass: HomeAssistant) -> None:
    """Test no devices error is handled."""
    user_input = {
        "api_host": "stips.api.staging.visionalization.net",
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
            new=AsyncMock(return_value=([], [])),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == "form"


async def test_unique_id_includes_api_host(hass: HomeAssistant) -> None:
    """Test same username on different API hosts can be configured separately."""
    existing_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{DOMAIN}_stips.api.staging.visionalization.net_demo",
        data={"api_host": "stips.api.staging.visionalization.net", "username": "demo"},
    )
    existing_entry.add_to_hass(hass)

    user_input = {
        "api_host": "stips.api.prod.visionalization.net",
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


async def test_duplicate_configuration_aborts(hass: HomeAssistant) -> None:
    """Test duplicate host/username combinations abort."""
    existing_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{DOMAIN}_stips.api.staging.visionalization.net_demo",
        data={"api_host": "stips.api.staging.visionalization.net", "username": "demo"},
    )
    existing_entry.add_to_hass(hass)

    user_input = {
        "api_host": "stips.api.staging.visionalization.net",
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

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
