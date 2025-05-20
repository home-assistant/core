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
            HomeAssistantError,
        ),
        (
            CredentialsInvalidError("Test error"),
            HomeAssistantError,
        ),
        (
            InvalidContentTypeError("Test error"),
            HomeAssistantError,
        ),
        (
            InvalidParameterError("Test error"),
            ServiceValidationError,
        ),
        (
            LoginError("Test error"),
            HomeAssistantError,
        ),
        (
            NoDataError("Test error"),
            HomeAssistantError,
        ),
        (
            NotSupportedError("Test error"),
            HomeAssistantError,
        ),
        (
            ReolinkConnectionError("Test error"),
            HomeAssistantError,
        ),
        (
            ReolinkError("Test error"),
            HomeAssistantError,
        ),
        (
            ReolinkTimeoutError("Test error"),
            HomeAssistantError,
        ),
        (
            SubscriptionError("Test error"),
            HomeAssistantError,
        ),
        (
            UnexpectedDataError("Test error"),
            HomeAssistantError,
        ),
    ],
)
async def test_try_function(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    side_effect: ReolinkError,
    expected: Exception,
) -> None:
    """Test try_function error translations using number entity."""
    reolink_connect.volume.return_value = 80

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.NUMBER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.NUMBER}.{TEST_NVR_NAME}_volume"

    reolink_connect.set_volume.side_effect = side_effect
    with pytest.raises(expected):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 50},
            blocking=True,
        )

    reolink_connect.set_volume.reset_mock(side_effect=True)
