"""Tests for the LIFX component."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from lifx import DiscoveredDevice, LifxError, LifxTimeoutError
import pytest

from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.const import CONF_SERIAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import IP_ADDRESS, SERIAL, _patch_config_flow_try_connect, async_setup_lifx_entry
from .helpers import create_mock_light

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_configuring_lifx_causes_discovery(hass: HomeAssistant) -> None:
    """Test that specifying empty config does discovery."""
    discovery_calls = 0

    async def mock_discover_devices(**kwargs: Any):
        """Yield a deterministic metadata-only discovery result."""
        nonlocal discovery_calls
        discovery_calls += 1
        yield DiscoveredDevice(serial="d073d5ddeecc", ip=IP_ADDRESS)

    with (
        _patch_config_flow_try_connect(),
        patch(
            "homeassistant.components.lifx.discovery.discover_devices",
            mock_discover_devices,
        ),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert discovery_calls == 0

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert discovery_calls == 1

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert discovery_calls == 2

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert discovery_calls == 3

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=30))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert discovery_calls == 4


async def test_setup_connects_once_using_stored_host_and_serial(
    hass: HomeAssistant,
) -> None:
    """Test setup makes one targeted connection with the stored entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)
    device = create_mock_light()
    with patch(
        "homeassistant.components.lifx.Device.connect", return_value=device
    ) as connect:
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    connect.assert_awaited_once_with(ip=IP_ADDRESS, serial=SERIAL)


async def test_setup_connection_error_schedules_retry_without_discovery(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a targeted connection error is preserved without discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)
    error = LifxError("connection failed")
    with patch(
        "homeassistant.components.lifx.Device.connect", side_effect=error
    ) as connect:
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    connect.assert_awaited_once_with(ip=IP_ADDRESS, serial=SERIAL)
    assert f"Unable to connect to the LIFX device at {IP_ADDRESS}" in caplog.text


async def test_config_entry_owns_one_persistent_device(hass: HomeAssistant) -> None:
    """Test setup refreshes and unload closes the persistent device."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    entry.add_to_hass(hass)
    device = create_mock_light()

    with patch(
        "homeassistant.components.lifx.Device.connect", return_value=device
    ) as connect:
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    connect.assert_awaited_once_with(ip=IP_ADDRESS, serial=SERIAL)
    device.refresh_state.assert_awaited_once_with()
    assert hass.states.get("light.my_group_my_bulb")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    device.close.assert_awaited_once_with()


async def test_device_is_named_after_its_label(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the device carries the label the bulb reports, group prefix and all."""
    device = create_mock_light()
    device.state.label = "My Group Downlight"

    await async_setup_lifx_entry(hass, device)

    registered = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert registered is not None
    assert registered.name == "My Group Downlight"
    assert hass.states.get("light.my_group_my_group_downlight")


async def test_first_refresh_failure_closes_device(hass: HomeAssistant) -> None:
    """Test a failed first refresh closes the connected device."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    entry.add_to_hass(hass)
    device = create_mock_light()
    device.refresh_state.side_effect = LifxTimeoutError("timed out")

    with patch("homeassistant.components.lifx.Device.connect", return_value=device):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    device.close.assert_awaited_once_with()


async def test_platform_setup_failure_closes_device(hass: HomeAssistant) -> None:
    """Test a failed platform setup closes the connected device."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    entry.add_to_hass(hass)
    device = create_mock_light()

    with (
        patch("homeassistant.components.lifx.Device.connect", return_value=device),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(side_effect=RuntimeError("platform failed")),
        ),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    device.close.assert_awaited_once_with()


async def test_unload_survives_an_unreachable_device(
    hass: HomeAssistant, mock_effect_conductor: MagicMock
) -> None:
    """Test a device that cannot be reached does not block unloading."""
    device = create_mock_light()
    entry = await async_setup_lifx_entry(hass, device)
    mock_effect_conductor.stop.side_effect = LifxTimeoutError("timed out")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    device.close.assert_awaited_once_with()


async def test_failed_unload_keeps_device_open(hass: HomeAssistant) -> None:
    """Test the device closes only after all platforms unload."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    entry.add_to_hass(hass)
    device = create_mock_light()
    with patch("homeassistant.components.lifx.Device.connect", return_value=device):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(entry.entry_id)

    device.close.assert_not_awaited()
