"""Tests for entity platform async_setup_entry and dynamic entity creation."""

from unittest.mock import MagicMock

import pytest
from custom_components.fritzbox_vpn import binary_sensor, sensor, switch
from custom_components.fritzbox_vpn.coordinator import FritzBoxVPNCoordinator
from custom_components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_VPN_CONNECTIONS


@pytest.mark.asyncio
async def test_switch_platform_setup(
    hass: HomeAssistant, coordinator_with_data, mock_config_entry: MockConfigEntry
) -> None:
    """Switch platform creates one entity per VPN connection."""
    added: list = []

    await switch.async_setup_entry(
        hass,
        mock_config_entry,
        lambda entities, **kwargs: added.extend(entities),
    )

    assert len(added) == len(MOCK_VPN_CONNECTIONS)


@pytest.mark.asyncio
async def test_sensor_platform_setup(
    hass: HomeAssistant, coordinator_with_data, mock_config_entry: MockConfigEntry
) -> None:
    """Sensor platform creates status and UID sensors per VPN."""
    added: list = []

    await sensor.async_setup_entry(
        hass,
        mock_config_entry,
        lambda entities, **kwargs: added.extend(entities),
    )

    assert len(added) == len(MOCK_VPN_CONNECTIONS) * 3


@pytest.mark.asyncio
async def test_binary_sensor_platform_setup(
    hass: HomeAssistant, coordinator_with_data, mock_config_entry: MockConfigEntry
) -> None:
    """Binary sensor platform creates connected sensors."""
    added: list = []

    await binary_sensor.async_setup_entry(
        hass,
        mock_config_entry,
        lambda entities, **kwargs: added.extend(entities),
    )

    assert len(added) == len(MOCK_VPN_CONNECTIONS)


@pytest.mark.asyncio
async def test_switch_adds_entity_on_coordinator_update(
    hass: HomeAssistant, coordinator_with_data, mock_config_entry: MockConfigEntry
) -> None:
    """Listener adds switch when a new VPN UID appears."""
    coordinator = mock_config_entry.runtime_data.coordinator
    captured_listener = None
    original_add_listener = coordinator.async_add_listener

    def _capture_listener(callback):
        nonlocal captured_listener
        captured_listener = callback
        return original_add_listener(callback)

    coordinator.async_add_listener = _capture_listener
    added: list = []
    await switch.async_setup_entry(
        hass,
        mock_config_entry,
        lambda entities, **kwargs: added.extend(entities),
    )
    initial_count = len(added)
    assert captured_listener is not None

    coordinator.data = {
        **MOCK_VPN_CONNECTIONS,
        "conn-new": {
            "uid": "wg-9",
            "name": "New VPN",
            "active": False,
            "connected": False,
        },
    }
    mock_config_entry.runtime_data.known_uids_switch = set(MOCK_VPN_CONNECTIONS.keys())

    captured_listener()
    await hass.async_block_till_done()

    assert len(added) > initial_count


@pytest.mark.asyncio
async def test_switch_setup_without_vpn_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Switch setup succeeds with empty coordinator data."""
    mock_config_entry.add_to_hass(hass)
    coordinator = FritzBoxVPNCoordinator(
        hass, mock_config_entry.data, None, mock_config_entry.entry_id
    )
    coordinator.async_set_updated_data({})
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    added: list = []
    await switch.async_setup_entry(
        hass,
        mock_config_entry,
        lambda entities, **kwargs: added.extend(entities),
    )
    assert added == []
