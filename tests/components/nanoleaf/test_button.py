"""Tests for the Nanoleaf button platform."""

from unittest.mock import AsyncMock, patch

from aionanoleaf2 import (
    AuthError,
    EndpointNotFoundError,
    InvalidResponseError,
    InvalidToken,
    NanoleafConnectionError,
    NanoleafError,
    NanoleafTimeoutError,
    NoAuthToken,
    Unavailable,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.nanoleaf.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import get_reauth_flows, setup_integration

ENTITY_ID = "button.nanoleaf_identify"


async def _press(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )


async def test_press_identifies_the_device(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing the button flashes the device."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await _press(hass)

    mock_nanoleaf.identify.assert_awaited_once()
    assert not get_reauth_flows(hass, mock_config_entry)


async def test_no_identify_button_without_event_support(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test devices without an event stream (Essentials) get no identify button."""
    mock_nanoleaf.supports_events = False

    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_stale_identify_button_is_removed_without_event_support(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the button created by earlier versions is removed from the registry."""
    mock_nanoleaf.supports_events = False
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        BUTTON_DOMAIN,
        DOMAIN,
        "ABCDEF123456_identify",
        config_entry=mock_config_entry,
        suggested_object_id="nanoleaf_identify",
    )
    assert entity_registry.async_get(ENTITY_ID) is not None

    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.BUTTON]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get(ENTITY_ID) is None


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(Unavailable("unavailable"), id="unavailable"),
        pytest.param(NanoleafConnectionError("connection"), id="connection"),
        pytest.param(NanoleafTimeoutError("timeout"), id="timeout"),
        pytest.param(InvalidResponseError("response"), id="invalid_response"),
        pytest.param(EndpointNotFoundError("identify"), id="endpoint_not_found"),
        pytest.param(NanoleafError("generic"), id="generic"),
    ],
)
async def test_press_maps_nanoleaf_errors(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: NanoleafError,
) -> None:
    """Test library errors become a Home Assistant error without reauth."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)
    mock_nanoleaf.identify.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press(hass)
    await hass.async_block_till_done()

    assert not isinstance(exc_info.value, ServiceValidationError)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "cannot_connect"
    assert exc_info.value.__cause__ is error
    assert not get_reauth_flows(hass, mock_config_entry)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(InvalidToken("invalid"), id="invalid_token"),
        pytest.param(AuthError("auth"), id="auth_error"),
        pytest.param(NoAuthToken("missing"), id="no_token"),
    ],
)
async def test_press_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: NanoleafError,
) -> None:
    """Test a rejected token raises a Home Assistant error and starts reauth."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)
    mock_nanoleaf.identify.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press(hass)
    await hass.async_block_till_done()

    assert exc_info.value.translation_key == "invalid_token"
    assert exc_info.value.__cause__ is error
    assert len(get_reauth_flows(hass, mock_config_entry)) == 1
