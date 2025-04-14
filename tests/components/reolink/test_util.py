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
from homeassistant.components.reolink.const import DOMAIN
from homeassistant.components.reolink.util import get_device_uid_and_ch
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .conftest import TEST_NVR_NAME, TEST_UID, TEST_UID_CAM

from tests.common import MockConfigEntry

DEV_ID_NVR = f"{TEST_UID}_{TEST_UID_CAM}"
DEV_ID_STANDALONE_CAM = f"{TEST_UID_CAM}"


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


@pytest.mark.parametrize(
    ("identifiers"),
    [
        ({(DOMAIN, DEV_ID_NVR), (DOMAIN, DEV_ID_STANDALONE_CAM)}),
        ({(DOMAIN, DEV_ID_STANDALONE_CAM), (DOMAIN, DEV_ID_NVR)}),
    ],
)
async def test_get_device_uid_and_ch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    device_registry: dr.DeviceRegistry,
    identifiers: set[tuple[str, str]],
) -> None:
    """Test get_device_uid_and_ch with multiple identifiers."""
    reolink_connect.channels = [0]

    dev_entry = device_registry.async_get_or_create(
        identifiers=identifiers,
        config_entry_id=config_entry.entry_id,
        disabled_by=None,
    )

    # setup CH 0 and host entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = get_device_uid_and_ch(dev_entry, config_entry.runtime_data.host)
    # always get the uid and channel form the DEV_ID_NVR since is_nvr = True
    assert result == ([TEST_UID, TEST_UID_CAM], 0, False)
