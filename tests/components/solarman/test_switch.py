"""Test the switch entity for Solarman."""

from unittest.mock import MagicMock, AsyncMock, patch
from datetime import timedelta
import pytest


from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    STATE_UNAVAILABLE,
    Platform
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import setup_integration
from homeassistant.components.solarman.const import DEFAULT_SCAN_INTERVAL

from tests.common import MockConfigEntry, snapshot_platform, async_fire_time_changed

@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_switch_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_solarman: MagicMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry
) -> None:
    with patch("homeassistant.components.solarman.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_turn_on_off(
    hass: HomeAssistant, 
    mock_solarman: MagicMock,
    mock_config_entry: MockConfigEntry
):
    with patch("homeassistant.components.solarman.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    entity_id = "switch.smart_plug_smart_plug"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )
    assert len(mock_solarman.set_status.mock_calls) == 1
    mock_solarman.set_status.assert_called_with(active=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )
    assert len(mock_solarman.set_status.mock_calls) == 2
    mock_solarman.set_status.assert_called_with(active=False)

@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
@pytest.mark.parametrize("status, expected_state", [
    ("on", "on"),
    ("off", "off"),
    (None, "unavailable"),
])
async def test_switch_state_cases(
    hass: HomeAssistant,
    mock_solarman: MagicMock,
    mock_config_entry: MockConfigEntry,
    status: str | None,
    expected_state: str,
):
    """Test all possible states of the switch."""
    mock_solarman.fetch_data.return_value = {"switch_status": status}
    
    with patch("homeassistant.components.solarman.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)
    
    entity_id = "switch.smart_plug_smart_plug"
    state = hass.states.get(entity_id)
    
    assert state.state == expected_state

@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_switch_availability(
    hass: HomeAssistant, mock_solarman: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    with patch("homeassistant.components.solarman.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    mock_solarman.fetch_data.side_effect = TimeoutError
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    await hass.async_block_till_done()

    assert (state := hass.states.get("switch.smart_plug_smart_plug"))
    assert state.state == STATE_UNAVAILABLE
