"""Test cases for the switcher_kis component."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.switcher_kis.const import DOMAIN, MAX_UPDATE_INTERVAL_SEC
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify

from . import init_integration
from .consts import (
    DUMMY_DEVICE_ID1,
    DUMMY_DEVICE_ID4,
    DUMMY_DEVICE_ID10,
    DUMMY_HEATER_DEVICE,
    DUMMY_IP_ADDRESS1,
    DUMMY_LIGHT_DEVICE,
    DUMMY_PLUG_DEVICE,
    DUMMY_SHUTTER_DEVICE,
    DUMMY_SWITCHER_DEVICES,
    DUMMY_THERMOSTAT_DEVICE,
    DUMMY_TOKEN as TOKEN,
    DUMMY_USERNAME as USERNAME,
)

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator


def _mock_probe_fail():
    """Patch the coordinator poll so it fails, as if the device is unreachable."""
    return patch(
        "homeassistant.components.switcher_kis.coordinator.SwitcherApi",
        side_effect=RuntimeError("fake poll error"),
    )


def _mock_probe_success():
    """Patch the coordinator poll so it answers, as if the device is reachable.

    Returns the patcher; its ``return_value`` is the mocked api used as an async
    context manager, so tests can assert which ``get_*_state`` call was made.
    """
    api = AsyncMock()
    api.__aenter__.return_value = api
    api.__aexit__.return_value = False
    return patch(
        "homeassistant.components.switcher_kis.coordinator.SwitcherApi",
        return_value=api,
    )


async def test_update_fail(
    hass: HomeAssistant,
    mock_bridge,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable when a broadcast stops and a poll fails."""
    entry = await init_integration(hass)
    assert mock_bridge

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 2

    with _mock_probe_fail():
        freezer.tick(timedelta(seconds=MAX_UPDATE_INTERVAL_SEC + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for device in DUMMY_SWITCHER_DEVICES:
        assert (
            f"Device {device.name} did not send an update for"
            f" {MAX_UPDATE_INTERVAL_SEC} seconds and did not answer a poll"
            in caplog.text
        )

        entity_id = f"switch.{slugify(device.name)}"
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

        entity_id = f"sensor.{slugify(device.name)}_power"
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=MAX_UPDATE_INTERVAL_SEC - 2)
    )
    await hass.async_block_till_done()

    for device in DUMMY_SWITCHER_DEVICES:
        entity_id = f"switch.{slugify(device.name)}"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE

        entity_id = f"sensor.{slugify(device.name)}_power"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE


async def test_update_fail_token_needed(
    hass: HomeAssistant,
    mock_bridge,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a token device becomes unavailable when broadcasts stop and a poll fails."""
    entry = await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    device = DUMMY_HEATER_DEVICE

    mock_bridge.mock_callbacks([DUMMY_HEATER_DEVICE])
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 1

    with _mock_probe_fail():
        freezer.tick(timedelta(seconds=MAX_UPDATE_INTERVAL_SEC + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert (
        f"Device {device.name} did not send an update for"
        f" {MAX_UPDATE_INTERVAL_SEC} seconds and did not answer a poll" in caplog.text
    )

    entity_id = f"switch.{slugify(device.name)}"
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    entity_id = f"sensor.{slugify(device.name)}_power"
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    mock_bridge.mock_callbacks([DUMMY_HEATER_DEVICE])
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=MAX_UPDATE_INTERVAL_SEC - 2)
    )
    await hass.async_block_till_done()

    entity_id = f"switch.{slugify(device.name)}"
    state = hass.states.get(entity_id)
    assert state.state != STATE_UNAVAILABLE

    entity_id = f"sensor.{slugify(device.name)}_power"
    state = hass.states.get(entity_id)
    assert state.state != STATE_UNAVAILABLE


async def test_poll_on_silence_keeps_available(
    hass: HomeAssistant,
    mock_bridge,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device that misses broadcasts but answers a poll stays available."""
    entry = await init_integration(hass)
    assert mock_bridge

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 2

    # No broadcast for the whole interval, but the TCP poll answers, so the
    # devices must stay available instead of flapping to unavailable.
    with _mock_probe_success():
        freezer.tick(timedelta(seconds=MAX_UPDATE_INTERVAL_SEC + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for device in DUMMY_SWITCHER_DEVICES:
        assert (
            f"Device {device.name} missed broadcasts but answered a poll" in caplog.text
        )
        assert entry.runtime_data[device.device_id].last_update_success is True

        entity_id = f"switch.{slugify(device.name)}"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("device", "probe_method"),
    [
        (DUMMY_THERMOSTAT_DEVICE, "get_breeze_state"),
        (DUMMY_SHUTTER_DEVICE, "get_shutter_state"),
        (DUMMY_LIGHT_DEVICE, "get_light_state"),
        (DUMMY_HEATER_DEVICE, "get_heater_state"),
        (DUMMY_PLUG_DEVICE, "get_state"),
    ],
)
async def test_poll_uses_category_probe(
    hass: HomeAssistant,
    mock_bridge,
    freezer: FrozenDateTimeFactory,
    device,
    probe_method: str,
) -> None:
    """Test the poll reads state with the api call for the device category."""
    entry = await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()
    assert len(entry.runtime_data) == 1

    with _mock_probe_success() as mock_api:
        freezer.tick(timedelta(seconds=MAX_UPDATE_INTERVAL_SEC + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    api = mock_api.return_value.__aenter__.return_value
    getattr(api, probe_method).assert_awaited_once_with()
    assert entry.runtime_data[device.device_id].last_update_success is True


async def test_poll_does_not_clobber_broadcast(
    hass: HomeAssistant,
    mock_bridge,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a broadcast arriving during the probe is preserved, not reverted."""
    entry = await init_integration(hass)
    assert mock_bridge

    mock_bridge.mock_callbacks([DUMMY_PLUG_DEVICE])
    await hass.async_block_till_done()

    coordinator = entry.runtime_data[DUMMY_PLUG_DEVICE.device_id]
    assert coordinator.data.ip_address == DUMMY_IP_ADDRESS1

    # A fresh broadcast lands mid-probe: the state read answers, but while it
    # runs a new device snapshot arrives and refreshes the coordinator data. The
    # update must return that fresh data, never the pre-probe snapshot.
    new_ip = "192.168.100.200"
    fresh_device = replace(DUMMY_PLUG_DEVICE, ip_address=new_ip)

    async def read_state_then_broadcast():
        coordinator.async_set_updated_data(fresh_device)

    with _mock_probe_success() as mock_api:
        mock_api.return_value.__aenter__.return_value.get_state.side_effect = (
            read_state_then_broadcast
        )
        freezer.tick(timedelta(seconds=MAX_UPDATE_INTERVAL_SEC + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert coordinator.data.ip_address == new_ip


async def test_entry_unload(hass: HomeAssistant, mock_bridge) -> None:
    """Test entry unload."""
    entry = await init_integration(hass)
    assert mock_bridge

    assert entry.state is ConfigEntryState.LOADED
    assert mock_bridge.is_running is True

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert mock_bridge.is_running is False


async def test_remove_device(
    hass: HomeAssistant,
    mock_bridge,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test being able to remove a disconnected device."""
    assert await async_setup_component(hass, "config", {})
    entry = await init_integration(hass)
    entry_id = entry.entry_id
    assert mock_bridge

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 2

    live_device_id = DUMMY_DEVICE_ID1
    dead_device_id = DUMMY_DEVICE_ID4

    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2

    # Create a dead device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, dead_device_id)},
        manufacturer="Switcher",
        model="Switcher Model",
        name="Switcher Device",
    )
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 3

    # Try to remove a live device - fails
    device = device_registry.async_get_device(identifiers={(DOMAIN, live_device_id)})
    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id, entry_id)
    assert not response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 3
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, live_device_id)})
        is not None
    )

    # Try to remove a dead device - succeeds
    device = device_registry.async_get_device(identifiers={(DOMAIN, dead_device_id)})
    response = await client.remove_device(device.id, entry_id)
    assert response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, dead_device_id)}) is None
    )


async def test_remove_device_token_needed(
    hass: HomeAssistant,
    mock_bridge,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test being able to remove a disconnected device."""
    assert await async_setup_component(hass, "config", {})
    entry = await init_integration(hass, USERNAME, TOKEN)
    entry_id = entry.entry_id
    assert mock_bridge

    mock_bridge.mock_callbacks([DUMMY_HEATER_DEVICE])
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 1

    live_device_id = DUMMY_DEVICE_ID10
    dead_device_id = DUMMY_DEVICE_ID4

    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1

    # Create a dead device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, dead_device_id)},
        manufacturer="Switcher",
        model="Switcher Model",
        name="Switcher Device",
    )
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2

    # Try to remove a live device - fails
    device = device_registry.async_get_device(identifiers={(DOMAIN, live_device_id)})
    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id, entry_id)
    assert not response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, live_device_id)})
        is not None
    )

    # Try to remove a dead device - succeeds
    device = device_registry.async_get_device(identifiers={(DOMAIN, dead_device_id)})
    response = await client.remove_device(device.id, entry_id)
    assert response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, dead_device_id)}) is None
    )
