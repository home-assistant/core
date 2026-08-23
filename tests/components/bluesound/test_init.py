"""Test bluesound integration."""

from pyblu.errors import PlayerUnreachableError

from homeassistant.components.bluesound import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import PlayerMocks

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, setup_config_entry: None, config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry."""
    assert hass.states.get("media_player.player_name1111").state == "playing"
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("media_player.player_name1111").state == "unavailable"
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_while_player_is_offline(
    hass: HomeAssistant,
    setup_config_entry: None,
    config_entry: MockConfigEntry,
    player_mocks: PlayerMocks,
) -> None:
    """Test entries can be unloaded correctly while the player is offline."""
    player_mocks.player_data.player.status.side_effect = PlayerUnreachableError(
        "Player not reachable"
    )
    player_mocks.player_data.status_long_polling_mock.trigger()

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("media_player.player_name1111").state == "unavailable"
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_non_default_port_links_to_leader_via_device_id(
    hass: HomeAssistant,
    setup_config_entry: None,
    config_entry_non_default_port: MockConfigEntry,
    player_mocks: PlayerMocks,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a non-default-port player links to the already-registered leader device."""
    config_entry_non_default_port.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_non_default_port.entry_id)
    await hass.async_block_till_done()

    assert config_entry_non_default_port.state is ConfigEntryState.LOADED

    leader_devices = device_registry.async_get_devices(
        identifiers={(DOMAIN, "ff:ff:01:01:01:01")}
    )
    assert leader_devices
    leader_device = leader_devices[0]

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ff:ff:01:01:01:01-11001"), config_entry_non_default_port.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == leader_device.id


async def test_non_default_port_without_leader_has_no_via_device_id(
    hass: HomeAssistant,
    config_entry_non_default_port: MockConfigEntry,
    player_mocks: PlayerMocks,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a non-default-port player sets up fine when the leader device is absent."""
    config_entry_non_default_port.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_non_default_port.entry_id)
    await hass.async_block_till_done()

    assert config_entry_non_default_port.state is ConfigEntryState.LOADED

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ff:ff:01:01:01:01-11001"), config_entry_non_default_port.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id is None
