"""Test Dremel 3D Printer integration."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectTimeout

from homeassistant.components.dremel_3d_printer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

MOCKED_MODEL = "homeassistant.components.dremel_3d_printer.Dremel3DPrinter.get_model"


@pytest.mark.parametrize("model", ["3D45", "3D20"])
async def test_setup(
    hass: HomeAssistant, connection, config_entry: MockConfigEntry, model: str
) -> None:
    """Test load and unload."""
    with patch(MOCKED_MODEL, return_value=model) as mock:
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert await async_setup_component(hass, DOMAIN, {})
    assert config_entry.state is ConfigEntryState.LOADED
    assert mock.called

    with patch(MOCKED_MODEL, return_value=model) as mock:
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
    assert mock.called


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, connection, config_entry: MockConfigEntry
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    with patch(
        "homeassistant.components.dremel_3d_printer.Dremel3DPrinter",
        side_effect=ConnectTimeout,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert await async_setup_component(hass, DOMAIN, {})
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_update_failed(
    hass: HomeAssistant, connection, config_entry: MockConfigEntry
) -> None:
    """Test coordinator throws UpdateFailed after failed update."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert await async_setup_component(hass, DOMAIN, {})
    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.dremel_3d_printer.Dremel3DPrinter.refresh",
        side_effect=RuntimeError,
    ) as updater:
        next_update = dt_util.utcnow() + timedelta(seconds=10)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
        updater.assert_called_once()
    state = hass.states.get("sensor.dremel_3d45_job_phase")
    assert state.state == STATE_UNAVAILABLE


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    connection,
    config_entry: MockConfigEntry,
) -> None:
    """Test device info."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert await async_setup_component(hass, DOMAIN, {})
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, config_entry.unique_id)}
    )

    assert device.manufacturer == "Dremel"
    assert device.model == "3D45"
    assert device.name == "DREMEL 3D45"
    assert device.sw_version == "v3.0_R02.12.10"
