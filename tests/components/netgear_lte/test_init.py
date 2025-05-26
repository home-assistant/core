"""Test Netgear LTE integration."""

from datetime import timedelta
from unittest.mock import patch

from eternalegypt.eternalegypt import Error
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import CONF_DATA

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("setup_integration")
async def test_setup_unload(hass: HomeAssistant) -> None:
    """Test setup and unload."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)


@pytest.mark.usefixtures("setup_cannot_connect")
async def test_async_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_integration")
async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device info."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.async_block_till_done()
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.unique_id)})
    assert device == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
async def test_update_failed(hass: HomeAssistant) -> None:
    """Test coordinator throws UpdateFailed after failed update."""
    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.information",
        side_effect=Error,
    ) as updater:
        next_update = dt_util.utcnow() + timedelta(seconds=10)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
        updater.assert_called_once()
    state = hass.states.get("sensor.netgear_lm1200_radio_quality")
    assert state.state == STATE_UNAVAILABLE
