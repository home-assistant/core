"""Tests for the diagnostics data provided by the Govee Bluetooth integration."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.govee_ble.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    GV5125_BUTTON_1_SERVICE_INFO,
    GVH5075_SERVICE_INFO,
    GVH5178_REMOTE_SERVICE_INFO,
)


@pytest.mark.parametrize(
    "service_info",
    [
        pytest.param(GVH5075_SERVICE_INFO, id="thermometer"),
        pytest.param(GVH5178_REMOTE_SERVICE_INFO, id="multi_sensor"),
        pytest.param(GV5125_BUTTON_1_SERVICE_INFO, id="button"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    service_info: BluetoothServiceInfo,
) -> None:
    """Test diagnostics for a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=service_info.address)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


async def test_diagnostics_no_advertisement(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics before any advertisement has been received."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=GVH5075_SERVICE_INFO.address)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
