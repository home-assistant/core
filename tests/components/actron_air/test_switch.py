"""Tests for the Actron Air switch platform."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config


async def test_switch_async_setup_entry(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch platform."""

    await add_mock_config(hass)

    status = mock_actron_api.state_manager.get_status.return_value

    # Test Away Mode Switch Entity
    entity_id = "switch.test_system_away_mode"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456-away_mode"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    status.user_aircon_settings.set_away_mode.assert_awaited_once_with(True)
    status.user_aircon_settings.set_away_mode.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    status.user_aircon_settings.set_away_mode.assert_awaited_once_with(False)
    status.user_aircon_settings.set_away_mode.reset_mock()

    # Test Continuous Fan Switch Entity
    entity_id = "switch.test_system_continuous_fan"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456-continuous_fan"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    status.user_aircon_settings.set_continuous_mode.assert_awaited_once_with(True)
    status.user_aircon_settings.set_continuous_mode.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    status.user_aircon_settings.set_continuous_mode.assert_awaited_once_with(False)
    status.user_aircon_settings.set_continuous_mode.reset_mock()

    # Test Quiet Mode Switch Entity
    entity_id = "switch.test_system_quiet_mode"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456-quiet_mode"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    status.user_aircon_settings.set_quiet_mode.assert_awaited_once_with(True)
    status.user_aircon_settings.set_quiet_mode.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    status.user_aircon_settings.set_quiet_mode.assert_awaited_once_with(False)
    status.user_aircon_settings.set_quiet_mode.reset_mock()

    # Test Turbo Mode Switch Entity
    entity_id = "switch.test_system_turbo_mode"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456-turbo_mode"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    status.user_aircon_settings.set_turbo_mode.assert_awaited_once_with(True)
    status.user_aircon_settings.set_turbo_mode.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    status.user_aircon_settings.set_turbo_mode.assert_awaited_once_with(False)
    status.user_aircon_settings.set_turbo_mode.reset_mock()


async def test_turbo_mode_not_supported(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turbo mode switch is not created when not supported."""
    status = mock_actron_api.state_manager.get_status.return_value
    status.user_aircon_settings.turbo_supported = False

    await add_mock_config(hass)

    entity_id = "switch.test_system_turbo_mode"
    assert not hass.states.get(entity_id)
    assert not entity_registry.async_get(entity_id)
