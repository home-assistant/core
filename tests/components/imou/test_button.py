"""Tests for Imou button platform."""

from unittest.mock import AsyncMock

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.imou.const import (
    PARAM_MUTE,
    PARAM_PTZ_UP,
    PARAM_RESTART_DEVICE,
    PARAM_STATE,
    PARAM_STATUS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

UNKNOWN_BUTTON_KEY = "legacy_unknown_button"


def _device_with_buttons(*button_keys: str) -> ImouHaDevice:
    """Build an online device exposing the given button ability keys."""
    device = ImouHaDevice("d1", "Device 1", "Imou", "m1", "1.0")
    for key in button_keys:
        device._buttons[key] = {}
    device._sensors[PARAM_STATUS] = {PARAM_STATE: DeviceStatus.ONLINE.value}
    return device


@pytest.mark.parametrize(
    "imou_mock_devices",
    [[_device_with_buttons(PARAM_MUTE, PARAM_PTZ_UP)]],
    indirect=True,
)
async def test_setup_creates_one_entity_per_supported_button(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    imou_integration: AsyncMock,
) -> None:
    """Each supported button type on a device becomes a button entity."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    keys = {e.translation_key for e in entries}
    assert keys == {PARAM_MUTE, PARAM_PTZ_UP}


@pytest.mark.parametrize(
    "imou_mock_devices",
    [[_device_with_buttons(UNKNOWN_BUTTON_KEY, PARAM_RESTART_DEVICE)]],
    indirect=True,
)
async def test_setup_ignores_unknown_button_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    imou_integration: AsyncMock,
) -> None:
    """Unknown button keys from the API are not turned into entities."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert len(entries) == 1
    assert entries[0].translation_key == PARAM_RESTART_DEVICE


@pytest.mark.parametrize(
    "imou_mock_devices",
    [[_device_with_buttons(PARAM_MUTE)]],
    indirect=True,
)
async def test_press_button_via_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    imou_integration: AsyncMock,
) -> None:
    """Pressing a button should call the vendor library through the coordinator."""
    states = hass.states.async_all("button")
    assert len(states) == 1
    entity_id = states[0].entity_id

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    imou_integration.async_press_button.assert_awaited_once()
    call = imou_integration.async_press_button.await_args
    assert call.args[1] == PARAM_MUTE


@pytest.mark.parametrize(
    "imou_mock_devices",
    [[_device_with_buttons(PARAM_MUTE)]],
    indirect=True,
)
async def test_press_button_service_propagates_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    imou_integration: AsyncMock,
) -> None:
    """Imou API errors from async_press_button surface to the service call."""
    imou_integration.async_press_button.side_effect = ImouException("cloud failure")

    states = hass.states.async_all("button")
    entity_id = states[0].entity_id

    with pytest.raises(HomeAssistantError, match="cloud failure"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
