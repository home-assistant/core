"""Test the Kiosker services."""

from typing import Any
from unittest.mock import MagicMock, patch

from kiosker import Blackout, ScreensaverState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kiosker.const import (
    ATTR_BACKGROUND,
    ATTR_BUTTON_BACKGROUND,
    ATTR_BUTTON_FOREGROUND,
    ATTR_BUTTON_TEXT,
    ATTR_DISMISSIBLE,
    ATTR_EXPIRE,
    ATTR_FOREGROUND,
    ATTR_ICON,
    ATTR_SOUND,
    ATTR_TEXT,
    ATTR_URL,
    ATTR_VISIBLE,
    DOMAIN,
)
from homeassistant.const import ATTR_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry

KIOSKER_DEVICE_ID = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"


async def _setup(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_kiosker_api.screensaver_get_state.return_value = ScreensaverState(
        visible=True, disabled=False
    )
    mock_kiosker_api.blackout_get.return_value = Blackout(visible=False)
    with patch("homeassistant.components.kiosker._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)


async def test_navigate_url(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test navigate_url service calls the API with the correct URL."""
    await _setup(hass, mock_kiosker_api, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, KIOSKER_DEVICE_ID)})
    assert device is not None

    await hass.services.async_call(
        DOMAIN,
        "navigate_url",
        {ATTR_DEVICE_ID: device.id, ATTR_URL: "https://example.com"},
        blocking=True,
    )

    assert mock_kiosker_api.navigate_url.call_args == snapshot


@pytest.mark.parametrize(
    "service_data",
    [
        pytest.param(
            {
                ATTR_VISIBLE: True,
                ATTR_TEXT: "Hello World",
                ATTR_BACKGROUND: [0, 0, 0],
                ATTR_FOREGROUND: [255, 255, 255],
                ATTR_ICON: "star",
                ATTR_EXPIRE: 30,
                ATTR_DISMISSIBLE: True,
                ATTR_BUTTON_BACKGROUND: [255, 0, 0],
                ATTR_BUTTON_FOREGROUND: [0, 255, 0],
                ATTR_BUTTON_TEXT: "Dismiss",
                ATTR_SOUND: "1007",
            },
            id="all_fields",
        ),
        pytest.param(
            {},
            id="defaults",
        ),
    ],
)
async def test_set_blackout(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    service_data: dict[str, Any],
) -> None:
    """Test set_blackout service builds the correct Blackout object."""
    await _setup(hass, mock_kiosker_api, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, KIOSKER_DEVICE_ID)})
    assert device is not None

    await hass.services.async_call(
        DOMAIN,
        "set_blackout",
        {ATTR_DEVICE_ID: device.id, **service_data},
        blocking=True,
    )

    assert mock_kiosker_api.blackout_set.call_args == snapshot


async def test_service_entry_not_loaded(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test services raise HomeAssistantError when the config entry is not loaded."""
    await _setup(hass, mock_kiosker_api, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, KIOSKER_DEVICE_ID)})
    assert device is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    with pytest.raises(HomeAssistantError, match="is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            "navigate_url",
            {ATTR_DEVICE_ID: device.id, ATTR_URL: "https://example.com"},
            blocking=True,
        )


async def test_service_non_kiosker_device(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test services raise HomeAssistantError when targeting a non-kiosker device."""
    await _setup(hass, mock_kiosker_api, mock_config_entry)

    other_config_entry = MockConfigEntry(domain="other_domain")
    other_config_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_config_entry.entry_id,
        identifiers={("other_domain", "other_device")},
    )

    with pytest.raises(HomeAssistantError, match=f"No {DOMAIN} devices"):
        await hass.services.async_call(
            DOMAIN,
            "navigate_url",
            {ATTR_DEVICE_ID: other_device.id, ATTR_URL: "https://example.com"},
            blocking=True,
        )
