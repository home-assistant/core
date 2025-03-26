"""Test the Reolink util functions."""

from unittest.mock import MagicMock, patch

import pytest
from reolink_aio.exceptions import (
    ApiError,
    CredentialsInvalidError,
    InvalidContentTypeError,
    InvalidParameterError,
    LoginError,
    NoDataError,
    NotSupportedError,
    ReolinkConnectionError,
    ReolinkError,
    ReolinkTimeoutError,
    SubscriptionError,
    UnexpectedDataError,
)

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import TEST_NVR_NAME

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (
            ApiError("Test error"),
            HomeAssistantError(translation_key="api_error"),
        ),
        (
            ApiError("Test error", translation_key="firmware_rate_limit"),
            HomeAssistantError(translation_key="firmware_rate_limit"),
        ),
        (
            ApiError("Test error", translation_key="not_in_strings.json"),
            HomeAssistantError(translation_key="api_error"),
        ),
        (
            CredentialsInvalidError("Test error"),
            HomeAssistantError(translation_key="invalid_credentials"),
        ),
        (
            InvalidContentTypeError("Test error"),
            HomeAssistantError(translation_key="invalid_content_type"),
        ),
        (
            InvalidParameterError("Test error"),
            ServiceValidationError(translation_key="invalid_parameter"),
        ),
        (
            LoginError("Test error"),
            HomeAssistantError(translation_key="login_error"),
        ),
        (
            NoDataError("Test error"),
            HomeAssistantError(translation_key="no_data"),
        ),
        (
            NotSupportedError("Test error"),
            HomeAssistantError(translation_key="not_supported"),
        ),
        (
            ReolinkConnectionError("Test error"),
            HomeAssistantError(translation_key="connection_error"),
        ),
        (
            ReolinkError("Test error"),
            HomeAssistantError(translation_key="unexpected"),
        ),
        (
            ReolinkTimeoutError("Test error"),
            HomeAssistantError(translation_key="timeout"),
        ),
        (
            SubscriptionError("Test error"),
            HomeAssistantError(translation_key="subscription_error"),
        ),
        (
            UnexpectedDataError("Test error"),
            HomeAssistantError(translation_key="unexpected_data"),
        ),
    ],
)
async def test_try_function(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    side_effect: ReolinkError,
    expected: HomeAssistantError,
) -> None:
    """Test try_function error translations using number entity."""
    reolink_connect.volume.return_value = 80

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.NUMBER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.NUMBER}.{TEST_NVR_NAME}_volume"

    reolink_connect.set_volume.side_effect = side_effect
    with pytest.raises(expected.__class__) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 50},
            blocking=True,
        )

    assert err.value.translation_key == expected.translation_key

    reolink_connect.set_volume.reset_mock(side_effect=True)
