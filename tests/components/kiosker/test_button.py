"""Test the Kiosker button platform."""

from unittest.mock import MagicMock, patch

from kiosker import Blackout, ScreensaverState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def _setup_button(
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


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all button entities."""
    await _setup_button(hass, mock_kiosker_api, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "api_method"),
    [
        ("button.kiosker_a98be1ce_ping", "ping"),
        ("button.kiosker_a98be1ce_refresh_page", "navigate_refresh"),
        ("button.kiosker_a98be1ce_go_home", "navigate_home"),
        ("button.kiosker_a98be1ce_go_forward", "navigate_forward"),
        ("button.kiosker_a98be1ce_go_back", "navigate_backward"),
        ("button.kiosker_a98be1ce_print_page", "print"),
        ("button.kiosker_a98be1ce_clear_cache", "clear_cache"),
        ("button.kiosker_a98be1ce_clear_cookies", "clear_cookies"),
        ("button.kiosker_a98be1ce_dismiss_screensaver", "screensaver_interact"),
    ],
)
async def test_press_button(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    api_method: str,
) -> None:
    """Test pressing buttons calls the correct API method."""
    await _setup_button(hass, mock_kiosker_api, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(mock_kiosker_api, api_method).assert_called_once()
