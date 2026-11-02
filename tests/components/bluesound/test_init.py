"""Test bluesound integration."""

from freezegun.api import FrozenDateTimeFactory
from pyblu import Preset
from pyblu.errors import PlayerUnreachableError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bluesound import DOMAIN
from homeassistant.components.bluesound.coordinator import (
    NODE_OFFLINE_CHECK_TIMEOUT,
    PRESET_AND_INPUTS_INTERVAL,
)
from homeassistant.components.media_player import ATTR_INPUT_SOURCE_LIST
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_PLAYING, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import PlayerMocks

ENTITY_ID = "media_player.player_name1111"


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


async def test_setup_entry_player_unreachable(
    hass: HomeAssistant, config_entry: MockConfigEntry, player_mocks: PlayerMocks
) -> None:
    """Test setup is retried when the player is unreachable."""
    player_mocks.player_data.player.sync_status.side_effect = PlayerUnreachableError(
        "Player not reachable"
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


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


async def test_log_when_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unavailability and recovery are each logged once."""
    status_mock = player_mocks.player_data.status_long_polling_mock
    sync_status_mock = player_mocks.player_data.sync_status_long_polling_mock

    status_mock.set_error(PlayerUnreachableError("Player not reachable"))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert (
        caplog.text.count("Error requesting player-name1111 data: Player not reachable")
        == 1
    )

    sync_status_mock.set_error(PlayerUnreachableError("Still not reachable"))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert "Still not reachable" not in caplog.text
    assert "Fetching player-name1111 data recovered" not in caplog.text

    # Both loops retry after the offline check timeout and succeed.
    status_mock.set_error(None)
    sync_status_mock.set_error(None)
    freezer.tick(NODE_OFFLINE_CHECK_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING
    assert caplog.text.count("Fetching player-name1111 data recovered") == 1


async def test_presets_and_inputs_updated(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test presets and inputs are polled periodically."""
    player_mocks.player_data.player.presets.return_value = [
        Preset("new_preset", 3, "url3", "image3", None)
    ]
    player_mocks.player_data.player.inputs.return_value = []

    freezer.tick(PRESET_AND_INPUTS_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST] == [
        "new_preset"
    ]


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(PlayerUnreachableError("Player not reachable"), id="unreachable"),
        pytest.param(ValueError("Unexpected error"), id="unexpected"),
    ],
)
async def test_presets_and_inputs_poll_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
    error: Exception,
) -> None:
    """Test the player goes unavailable when polling presets fails."""
    player_mocks.player_data.player.presets.side_effect = error

    freezer.tick(PRESET_AND_INPUTS_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "long_polling_mock",
    ["status_long_polling_mock", "sync_status_long_polling_mock"],
)
async def test_unexpected_error_while_polling(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
    long_polling_mock: str,
) -> None:
    """Test the player goes unavailable on an unexpected polling error."""
    getattr(player_mocks.player_data, long_polling_mock).set_error(
        ValueError("Unexpected error")
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
