"""Tests for switches."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from ohme import ChargerStatus
from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the Ohme switches."""
    with patch("homeassistant.components.ohme.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that switch shows as unavailable when a charge is not in progress."""
    mock_client.status = ChargerStatus.PLUGGED_IN
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.ohme_home_pro_pause_charge")
    assert state.state == STATE_OFF

    mock_client.status = ChargerStatus.UNPLUGGED
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.ohme_home_pro_pause_charge")
    assert state.state == STATE_UNAVAILABLE


async def test_switch_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the switch turn_on action."""
    mock_client.status = ChargerStatus.PENDING_APPROVAL
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "switch.ohme_home_pro_max_charge",
        },
        blocking=True,
    )

    assert len(mock_client.async_max_charge.mock_calls) == 1


async def test_switch_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the switch turn_off action."""
    mock_client.status = ChargerStatus.PENDING_APPROVAL
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "switch.ohme_home_pro_max_charge",
        },
        blocking=True,
    )

    assert len(mock_client.async_max_charge.mock_calls) == 1
