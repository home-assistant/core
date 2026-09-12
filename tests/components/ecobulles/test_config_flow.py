"""Tests for the Ecobulles config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.ecobulles.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.ecobulles.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


USER_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "secret",
}

FLOW_INFO = {
    "title": "Ecobulles : Test box",
    "user_id": "user-id",
    "eco_ref": "test-eco-ref",
    "name": "Test box",
    "firmware_version": "1.0",
    "num_serie": "XC240007",
}

DEVICE_INFO = {
    "data": {
        "boite": {
            "name": "Test box",
            "firm_ver": "1.0",
            "num_serie": "XC240007",
        }
    }
}


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Successful setup creates a config entry."""
    with (
        patch(
            "homeassistant.components.ecobulles.config_flow.validate_input",
            AsyncMock(return_value=FLOW_INFO),
        ),
        patch(
            "homeassistant.components.ecobulles.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == FLOW_INFO["title"]
    assert result["data"][CONF_EMAIL] == USER_INPUT[CONF_EMAIL]
    assert result["data"][CONF_PASSWORD] == USER_INPUT[CONF_PASSWORD]
    assert result["data"]["eco_ref"] == "test-eco-ref"
    assert result["data"]["user_id"] == "user-id"
    assert result["data"]["name"] == "Test box"
    assert result["data"]["firmware_version"] == "1.0"
    assert result["data"]["num_serie"] == "XC240007"
    assert result["result"].unique_id == "test-eco-ref"


async def test_user_flow_handles_connection_error(hass: HomeAssistant) -> None:
    """Connection errors are surfaced on the form."""
    with patch(
        "homeassistant.components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=CannotConnect()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_handles_invalid_auth(hass: HomeAssistant) -> None:
    """Invalid auth is surfaced on the form."""
    with patch(
        "homeassistant.components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=InvalidAuth()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_handles_unknown_error(hass: HomeAssistant) -> None:
    """Unexpected validation errors are surfaced on the form."""
    with patch(
        "homeassistant.components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=ValueError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_rejects_existing_entry(hass: HomeAssistant) -> None:
    """Adding an already-known device aborts the flow."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**USER_INPUT, "eco_ref": "test-eco-ref"},
        unique_id="test-eco-ref",
    )
    existing_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ecobulles.config_flow.validate_input",
        AsyncMock(return_value=FLOW_INFO),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_user_flow_without_input_shows_form(hass: HomeAssistant) -> None:
    """The first user step shows a form before credentials are submitted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_validate_input_normalizes_success(hass: HomeAssistant) -> None:
    """validate_input returns normalized metadata after authentication."""
    with (
        patch(
            "homeassistant.components.ecobulles.config_flow.EcobullesClient.authenticate",
            AsyncMock(return_value=(True, "user-id", "eco-ref", "Box")),
        ),
        patch(
            "homeassistant.components.ecobulles.config_flow.EcobullesClient.get_device_info",
            AsyncMock(return_value=DEVICE_INFO),
        ),
    ):
        assert await validate_input(hass, USER_INPUT) == {
            "title": "Ecobulles : Test box",
            "user_id": "user-id",
            "eco_ref": "eco-ref",
            "name": "Test box",
            "firmware_version": "1.0",
            "num_serie": "XC240007",
        }


async def test_validate_input_uses_box_name_for_title_when_auth_name_missing(
    hass: HomeAssistant,
) -> None:
    """validate_input uses the resolved device name consistently."""
    with (
        patch(
            "homeassistant.components.ecobulles.config_flow.EcobullesClient.authenticate",
            AsyncMock(return_value=(True, "user-id", "eco-ref", "   ")),
        ),
        patch(
            "homeassistant.components.ecobulles.config_flow.EcobullesClient.get_device_info",
            AsyncMock(return_value=DEVICE_INFO),
        ),
    ):
        result = await validate_input(hass, USER_INPUT)

    assert result["title"] == "Ecobulles : Test box"
    assert result["name"] == "Test box"


async def test_validate_input_maps_runtime_errors(hass: HomeAssistant) -> None:
    """Low-level API runtime errors become cannot-connect errors."""
    with (
        patch(
            "homeassistant.components.ecobulles.config_flow.EcobullesClient.authenticate",
            AsyncMock(side_effect=RuntimeError("network")),
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(hass, USER_INPUT)


async def test_validate_input_maps_timeout_errors(hass: HomeAssistant) -> None:
    """Low-level API timeouts become cannot-connect errors."""
    with (
        patch(
            "homeassistant.components.ecobulles.config_flow.EcobullesClient.authenticate",
            AsyncMock(side_effect=TimeoutError),
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(hass, USER_INPUT)


async def test_validate_input_rejects_invalid_auth(hass: HomeAssistant) -> None:
    """Authentication failures become invalid-auth errors."""
    with (
        patch(
            "homeassistant.components.ecobulles.config_flow.EcobullesClient.authenticate",
            AsyncMock(return_value=(False, None, None, None)),
        ),
        pytest.raises(InvalidAuth),
    ):
        await validate_input(hass, USER_INPUT)
