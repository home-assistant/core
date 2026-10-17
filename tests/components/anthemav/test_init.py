"""Test the Anthem A/V Receivers config flow."""

from collections.abc import Callable
from unittest.mock import ANY, AsyncMock, call, patch

from anthemav.device_error import DeviceError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.anthemav.const import DOMAIN, POLL_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MODEL, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_connection_create: AsyncMock,
    mock_anthemav: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test load and unload AnthemAv component."""
    # assert avr is created
    mock_connection_create.assert_called_with(
        host="1.1.1.1", port=14999, update_callback=ANY
    )
    assert init_integration.state is ConfigEntryState.LOADED

    # unload
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    # assert unload and avr is closed
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_anthemav.close.assert_called_once()


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00:00:00:00:00:01"), init_integration.entry_id
    )
    assert device_entry
    assert device_entry == snapshot

    zone_2_device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00:00:00:00:00:01_2"), init_integration.entry_id
    )
    assert zone_2_device_entry
    assert zone_2_device_entry.via_device_id == device_entry.id


@pytest.mark.parametrize("error", [OSError, DeviceError])
async def test_config_entry_not_ready_when_oserror(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, error: Exception
) -> None:
    """Test AnthemAV configuration entry not ready."""
    with patch(
        "anthemav.Connection.create",
        side_effect=error,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_anthemav_dispatcher_signal(
    hass: HomeAssistant,
    mock_connection_create: AsyncMock,
    mock_anthemav: AsyncMock,
    init_integration: MockConfigEntry,
    update_callback: Callable[[str], None],
) -> None:
    """Test send update signal to dispatcher."""
    states = hass.states.get("media_player.anthem_av")
    assert states
    assert states.state == STATE_OFF

    # change state of the AVR
    mock_anthemav.protocol.zones[1].power = True

    update_callback("power")

    await hass.async_block_till_done()

    states = hass.states.get("media_player.anthem_av")
    assert states.state == STATE_ON


async def _setup_with_model(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, model: str
) -> None:
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_MODEL: model}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_connection_create")
async def test_poll_x10_zones(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test MRX x10 zones are polled, with volume and mute only when powered on."""
    mock_config_entry.add_to_hass(hass)
    # The receiver reports its model with a trailing space.
    await _setup_with_model(hass, mock_config_entry, "MRX 310 ")
    zone_1, zone_2 = mock_anthemav.protocol.zones.values()
    zone_1.power = True

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert zone_1.query.call_args_list == [call("POW"), call("VOL"), call("MUT")]
    assert zone_2.query.call_args_list == [call("POW")]

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    zone_1.query.reset_mock()
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Polling stops once the entry is unloaded.
    zone_1.query.assert_not_called()


@pytest.mark.usefixtures("mock_connection_create")
async def test_poll_x10_skipped_when_disconnected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test polling is skipped while the connection is down."""
    mock_config_entry.add_to_hass(hass)
    await _setup_with_model(hass, mock_config_entry, "MRX 310 ")
    mock_anthemav.protocol.transport = None

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for zone in mock_anthemav.protocol.zones.values():
        zone.query.assert_not_called()


@pytest.mark.usefixtures("mock_connection_create")
async def test_no_poll_for_push_models(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_anthemav: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test models that push their state are not polled."""
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for zone in mock_anthemav.protocol.zones.values():
        zone.query.assert_not_called()
