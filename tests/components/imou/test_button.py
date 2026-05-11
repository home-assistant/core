"""Tests for Imou button platform."""

from unittest.mock import AsyncMock, MagicMock

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice
import pytest

from homeassistant.components.imou import button as imou_button
from homeassistant.components.imou.button import ImouButton
from homeassistant.components.imou.const import (
    PARAM_MUTE,
    PARAM_PTZ_UP,
    PARAM_RESTART_DEVICE,
)
from homeassistant.components.imou.coordinator import ImouDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .util import CONFIG_ENTRY_DATA

from tests.common import MockConfigEntry

UNKNOWN_BUTTON_KEY = "legacy_unknown_button"


def _make_device_with_buttons(
    *button_keys: str,
) -> ImouHaDevice:
    """Build a device with the given button ability keys in the buttons map."""
    device = ImouHaDevice("d1", "Device 1", "Imou", "m1", "1.0")
    for key in button_keys:
        device._buttons[key] = {}
    return device


async def test_async_setup_entry_adds_one_entity_per_button(
    hass: HomeAssistant,
) -> None:
    """Each supported button type on a device becomes an entity."""
    entry = MockConfigEntry(
        domain="imou",
        data=CONFIG_ENTRY_DATA,
        entry_id="entry-btn",
    )
    mock_manager = MagicMock()
    coordinator = ImouDataUpdateCoordinator(hass, mock_manager, entry)
    device = _make_device_with_buttons(PARAM_MUTE, PARAM_PTZ_UP)
    coordinator._devices = [device]
    entry.runtime_data = coordinator

    added: list[ImouButton] = []

    def _add(entities: object, **_kwargs: object) -> None:
        added.extend(entities)  # type: ignore[arg-type]

    await imou_button.async_setup_entry(hass, entry, _add)

    types = {e.translation_key for e in added}
    assert types == {PARAM_MUTE, PARAM_PTZ_UP}


async def test_async_setup_entry_ignores_unknown_button_types(
    hass: HomeAssistant,
) -> None:
    """Unknown button keys from the API are not turned into entities."""
    entry = MockConfigEntry(
        domain="imou",
        data=CONFIG_ENTRY_DATA,
        entry_id="entry-btn-2",
    )
    mock_manager = MagicMock()
    coordinator = ImouDataUpdateCoordinator(hass, mock_manager, entry)
    device = _make_device_with_buttons(UNKNOWN_BUTTON_KEY, PARAM_RESTART_DEVICE)
    coordinator._devices = [device]
    entry.runtime_data = coordinator

    added: list[ImouButton] = []

    def _add(entities: object, **_kwargs: object) -> None:
        added.extend(entities)  # type: ignore[arg-type]

    await imou_button.async_setup_entry(hass, entry, _add)

    assert len(added) == 1
    assert added[0].translation_key == PARAM_RESTART_DEVICE


@pytest.mark.usefixtures("hass")
async def test_async_press_calls_device_manager() -> None:
    """Press delegates to the HA device manager."""
    mock_manager = MagicMock()
    mock_manager.async_press_button = AsyncMock()
    coordinator = MagicMock(spec=ImouDataUpdateCoordinator)
    coordinator.device_manager = mock_manager

    device = _make_device_with_buttons(PARAM_MUTE)
    entity = ImouButton(coordinator, PARAM_MUTE, device)

    await entity.async_press()

    mock_manager.async_press_button.assert_awaited_once_with(device, PARAM_MUTE, 500)


@pytest.mark.usefixtures("hass")
async def test_async_press_raises_home_assistant_error() -> None:
    """Imou API errors become HomeAssistantError."""
    mock_manager = MagicMock()
    mock_manager.async_press_button = AsyncMock(
        side_effect=ImouException("cloud failure")
    )
    coordinator = MagicMock(spec=ImouDataUpdateCoordinator)
    coordinator.device_manager = mock_manager

    device = _make_device_with_buttons(PARAM_MUTE)
    entity = ImouButton(coordinator, PARAM_MUTE, device)

    with pytest.raises(HomeAssistantError, match="cloud failure"):
        await entity.async_press()
