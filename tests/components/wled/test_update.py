"""Tests for the WLED update platform."""

from unittest.mock import MagicMock

import pytest
from wled import WLEDError

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_TITLE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_update_available(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the firmware update available."""
    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == UpdateDeviceClass.FIRMWARE
    assert state.state == STATE_ON
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/wled/icon.png"
    )
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.8.5"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.12.0"
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    assert (
        state.attributes[ATTR_RELEASE_URL]
        == "https://github.com/Aircoookie/WLED/releases/tag/v0.12.0"
    )
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
    )
    assert state.attributes[ATTR_TITLE] == "WLED"
    assert ATTR_ICON not in state.attributes

    assert (entry := entity_registry.async_get("update.wled_rgb_light_firmware"))
    assert entry.unique_id == "aabbccddeeff"
    assert entry.entity_category is EntityCategory.CONFIG


@pytest.mark.parametrize("device_fixture", ["rgb_no_update"])
async def test_update_information_available(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test having no update information available at all."""
    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == UpdateDeviceClass.FIRMWARE
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_INSTALLED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] is None
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    assert state.attributes[ATTR_RELEASE_URL] is None
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
    )
    assert state.attributes[ATTR_TITLE] == "WLED"
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("update.wled_rgb_light_firmware")
    assert entry
    assert entry.unique_id == "aabbccddeeff"
    assert entry.entity_category is EntityCategory.CONFIG


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_no_update_available(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test there is no update available."""
    assert (state := hass.states.get("update.wled_websocket_firmware"))
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_DEVICE_CLASS) == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.12.0-b2"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.12.0-b2"
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    assert (
        state.attributes[ATTR_RELEASE_URL]
        == "https://github.com/Aircoookie/WLED/releases/tag/v0.12.0-b2"
    )
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
    )
    assert state.attributes[ATTR_TITLE] == "WLED"
    assert ATTR_ICON not in state.attributes

    assert ATTR_ICON not in state.attributes

    assert (entry := entity_registry.async_get("update.wled_websocket_firmware"))
    assert entry.unique_id == "aabbccddeeff"
    assert entry.entity_category is EntityCategory.CONFIG


async def test_update_error(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED update."""
    mock_wled.update.side_effect = WLEDError

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.wled_rgb_light_firmware"},
        blocking=True,
    )

    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.state == STATE_UNAVAILABLE
    assert "Invalid response from API" in caplog.text


async def test_update_stay_stable(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the update entity staying on stable.

    There is both an update for beta and stable available, however, the device
    is currently running a stable version. Therefore, the update entity should
    update to the next stable (even though beta is newer).
    """
    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.8.5"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.12.0"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.wled_rgb_light_firmware"},
        blocking=True,
    )
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="0.12.0")


@pytest.mark.parametrize("device_fixture", ["rgbw"])
async def test_update_beta_to_stable(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the update entity.

    There is both an update for beta and stable available and the device
    is currently a beta, however, a newer stable is available. Therefore, the
    update entity should update to the next stable.
    """
    assert (state := hass.states.get("update.wled_rgbw_light_firmware"))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.8.6b4"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.8.6"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.wled_rgbw_light_firmware"},
        blocking=True,
    )
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="0.8.6")


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
async def test_update_stay_beta(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the update entity.

    There is an update for beta and the device is currently a beta. Therefore,
    the update entity should update to the next beta.
    """
    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.8.6b1"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.8.6b2"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.wled_rgb_light_firmware"},
        blocking=True,
    )
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="0.8.6b2")
