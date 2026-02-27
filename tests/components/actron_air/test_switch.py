"""Tests for the Actron Air switch platform."""

from unittest.mock import MagicMock, patch

from actron_neo_api import ActronAirAPIError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switch_entities(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch entities."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("switch.test_system_away_mode", "set_away_mode"),
        ("switch.test_system_continuous_fan", "set_continuous_mode"),
        ("switch.test_system_quiet_mode", "set_quiet_mode"),
        ("switch.test_system_turbo_mode", "set_turbo_mode"),
    ],
)
async def test_switch_toggles(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
) -> None:
    """Test switch toggles."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    status = mock_actron_api.state_manager.get_status.return_value
    mock_method = getattr(status.user_aircon_settings, method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_method.assert_awaited_once_with(True)
    mock_method.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_method.assert_awaited_once_with(False)


async def test_turbo_mode_not_supported(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turbo mode switch is not created when not supported."""
    status = mock_actron_api.state_manager.get_status.return_value
    status.user_aircon_settings.turbo_supported = False

    await setup_integration(hass, mock_config_entry)

    entity_id = "switch.test_system_turbo_mode"
    assert not hass.states.get(entity_id)
    assert not entity_registry.async_get(entity_id)


@pytest.mark.parametrize(
    ("entity_id", "method", "service"),
    [
        ("switch.test_system_away_mode", "set_away_mode", SERVICE_TURN_ON),
        ("switch.test_system_continuous_fan", "set_continuous_mode", SERVICE_TURN_OFF),
        ("switch.test_system_quiet_mode", "set_quiet_mode", SERVICE_TURN_ON),
        ("switch.test_system_turbo_mode", "set_turbo_mode", SERVICE_TURN_OFF),
    ],
)
async def test_switch_api_error(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
    service: str,
) -> None:
    """Test API error handling when toggling switches."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    status = mock_actron_api.state_manager.get_status.return_value
    mock_method = getattr(status.user_aircon_settings, method)
    mock_method.side_effect = ActronAirAPIError("Test error")

    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
