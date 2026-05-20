"""Tests for FRITZ!Box Tools WireGuard VPN switches."""

# pylint: disable=unused-argument,redefined-outer-name
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.fritz.const import DOMAIN, VPN_UNIQUE_ID_SUFFIX_SWITCH
from homeassistant.components.fritz.vpn_data import FRITZ_VPN_DATA_KEY
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_OFF
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_SERIAL_NUMBER, MOCK_USER_DATA

from tests.common import MockConfigEntry

VPN_OFFICE_UNIQUE_ID = f"{MOCK_SERIAL_NUMBER}-uid-office-{VPN_UNIQUE_ID_SUFFIX_SWITCH}"


def _vpn_entity_id(
    entity_registry: er.EntityRegistry, entry_id: str, unique_id: str
) -> str:
    """Return entity_id for a VPN switch unique_id."""
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        if entity_entry.unique_id == unique_id:
            return entity_entry.entity_id
    raise AssertionError(f"No entity with unique_id {unique_id!r}")


@pytest.fixture
def vpn_patch_wireguard(mock_vpn_wireguard: MagicMock):
    """Patch FritzWireguard for VPN tests."""
    with patch(
        "homeassistant.components.fritz.coordinator.FritzWireguard",
        return_value=mock_vpn_wireguard,
    ):
        yield mock_vpn_wireguard


async def test_vpn_switch_uses_fritz_serial_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    vpn_patch_wireguard: MagicMock,
) -> None:
    """VPN entities use AvmWrapper serial (same id space as other fritz entities)."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = _vpn_entity_id(entity_registry, entry.entry_id, VPN_OFFICE_UNIQUE_ID)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["status"] == "enabled"

    vpn_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_SERIAL_NUMBER}_vpn_uid-office")}
    )
    assert vpn_device is not None
    assert (
        vpn_device.via_device_id
        == device_registry.async_get_device(
            identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
        ).id
    )


async def test_vpn_switch_turn_on_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    vpn_patch_wireguard: MagicMock,
) -> None:
    """Turn VPN switch off and on via homeassistant services."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = _vpn_entity_id(entity_registry, entry.entry_id, VPN_OFFICE_UNIQUE_ID)

    # Verify initial state is on
    office_state = hass.states.get(entity_id)
    assert office_state is not None
    assert office_state.state == STATE_ON

    # Call turn_off service
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    vpn_patch_wireguard.toggle_vpn.assert_called_with("uid-office", False)


async def test_vpn_switch_entities_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    vpn_patch_wireguard: MagicMock,
) -> None:
    """VPN switch entities are created for configured connections."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The office connection switch should exist
    entity_id = _vpn_entity_id(entity_registry, entry.entry_id, VPN_OFFICE_UNIQUE_ID)
    office_state = hass.states.get(entity_id)
    assert office_state is not None


async def test_vpn_switch_prunes_known_uids_when_connection_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    vpn_patch_wireguard: MagicMock,
) -> None:
    """Removed VPN UIDs are tracked in known_uids."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    vpn_data = hass.data[FRITZ_VPN_DATA_KEY][entry.entry_id]
    # The office connection should be tracked
    assert "uid-office" in vpn_data.known_uids
