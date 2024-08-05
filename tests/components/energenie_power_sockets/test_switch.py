"""Test the switch functionality."""

from unittest.mock import MagicMock

from pyegps.exceptions import EgpsException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energenie_power_sockets.const import DOMAIN
from homeassistant.components.homeassistant import (
    DOMAIN as HOME_ASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def _test_switch_on_off(
    hass: HomeAssistant, entity_id: str, dev: MagicMock
) -> None:
    """Call switch on/off service."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == STATE_OFF


async def _test_switch_on_exeception(
    hass: HomeAssistant, entity_id: str, dev: MagicMock
) -> None:
    """Call switch on service with USBError side effect."""
    dev.switch_on.side_effect = EgpsException
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HOME_ASSISTANT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": entity_id},
            blocking=True,
        )
    dev.switch_on.side_effect = None


async def _test_switch_off_exeception(
    hass: HomeAssistant, entity_id: str, dev: MagicMock
) -> None:
    """Call switch off service with USBError side effect."""
    dev.switch_off.side_effect = EgpsException
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": entity_id},
            blocking=True,
        )
    dev.switch_off.side_effect = None


async def _test_switch_update_exception(
    hass: HomeAssistant, entity_id: str, dev: MagicMock
) -> None:
    """Call switch update with USBError side effect."""
    dev.get_status.side_effect = EgpsException
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {"entity_id": entity_id},
            blocking=True,
        )
    dev.get_status.side_effect = None


@pytest.mark.parametrize(
    "entity_name",
    [
        "mockedusbdevice_socket_0",
        "mockedusbdevice_socket_1",
        "mockedusbdevice_socket_2",
        "mockedusbdevice_socket_3",
    ],
)
async def test_switch_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    valid_config_entry: MockConfigEntry,
    mock_get_device: MagicMock,
    entity_name: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup and functionality of device switches."""

    entry = valid_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]

    state = hass.states.get(f"switch.{entity_name}")
    assert state == snapshot
    assert entity_registry.async_get(state.entity_id) == snapshot

    device_mock = mock_get_device.return_value
    await _test_switch_on_off(hass, state.entity_id, device_mock)
    await _test_switch_on_exeception(hass, state.entity_id, device_mock)
    await _test_switch_off_exeception(hass, state.entity_id, device_mock)
    await _test_switch_update_exception(hass, state.entity_id, device_mock)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
