"""Tests for BroadLink Magic setup and remote entities."""

from unittest.mock import MagicMock, patch

from broadlink_magic import MSG_HEARTBEAT, pack_message
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.broadlink_magic_home.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from . import setup_integration

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def test_setup_registry_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test family setup, device topology, stale cleanup, and unload."""
    config_entry.add_to_hass(hass)
    stale_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "stale-device")},
        name="Stale device",
    )
    stale_entity = entity_registry.async_get_or_create(
        "light",
        DOMAIN,
        "stale-entity",
        config_entry=config_entry,
        device_id=stale_device.id,
        suggested_object_id="stale",
    )
    stale_group_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "device:family-1_group_65")},
        name="Old light group",
    )
    stale_group_entity = entity_registry.async_get_or_create(
        "light",
        DOMAIN,
        "family-1_group_65_light",
        config_entry=config_entry,
        device_id=stale_group_device.id,
        suggested_object_id="old_light_group",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert entity_registry.async_get(stale_entity.entity_id) is None
    assert entity_registry.async_get(stale_group_entity.entity_id) is None
    assert device_registry.async_get(stale_device.id) is None
    assert device_registry.async_get(stale_group_device.id) is None
    family_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "family:family-1"), config_entry_id=config_entry.entry_id
    )
    assert family_device is not None
    whole_home_area = area_registry.async_get_area_by_name("Whole home")
    assert whole_home_area is not None
    assert family_device.area_id == whole_home_area.id
    for mac in ("aabbccddeeff", "112233445566"):
        gateway = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"gateway:{mac}"), config_entry_id=config_entry.entry_id
        )
        assert gateway is not None
        assert gateway.via_device_id == family_device.id

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_coordinator_allows_offline_family_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an update succeeds while entities remain unavailable."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert not coordinator.gateway_set.online_gateways
    state = hass.states.get("climate.whole_home_air_conditioner")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("target", "error", "state"),
    [
        (
            "homeassistant.components.broadlink_magic_home.FamilyCoordinator."
            "async_config_entry_first_refresh",
            ConfigEntryNotReady,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            RuntimeError,
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_failed_setup_releases_gateway_routes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_gateway_listener: MagicMock,
    target: str,
    error: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test a failed family setup unregisters its gateway routes."""
    config_entry.add_to_hass(hass)
    with patch(target, side_effect=error):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is state
    mock_gateway_listener.register_gateway_set.assert_called_once()
    mock_gateway_listener.async_unregister_entry.assert_awaited_once_with(
        config_entry.entry_id
    )


async def test_gateway_port_unavailable_retries_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a busy gateway port lets Home Assistant retry the family setup."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.broadlink_magic_home.async_get_gateway_listener",
        side_effect=OSError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_inbound_gateway_address_is_runtime_only(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a gateway peer change is not persisted in config entry data."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    gateway_set = config_entry.runtime_data.gateway_set
    gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(
            MSG_HEARTBEAT,
            1,
            bytes.fromhex("aabbccddeeff"),
        ),
        ("192.0.2.200", 41001),
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert gateway_set.online_gateways[0].peer == ("192.0.2.200", 41001)
    addresses = {
        gateway["mac"]: gateway["host"] for gateway in config_entry.data["gateways"]
    }
    assert addresses["aabbccddeeff"] == "192.0.2.10"
    assert addresses["112233445566"] == "192.0.2.11"


async def test_unknown_and_empty_reports_are_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reports for unknown addresses or without values change nothing."""
    coordinator = await setup_integration(hass, config_entry)

    coordinator._handle_fastcon_report(0x7FFF, b"\x01")
    coordinator._handle_fastcon_report(257, b"")

    assert coordinator.report_serials == {}
    assert coordinator.device_states == {}
