"""Tests for the diagnostics data provided by the Tasmota integration."""

import copy
import json

import pytest
from pytest_homeassistant.common import async_fire_mqtt_message
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_device
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tasmota.const import DEFAULT_PREFIX, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .test_common import DEFAULT_CONFIG


@pytest.mark.usefixtures("mqtt_mock", "setup_tasmota")
async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device diagnostics."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    mac = config["mac"]
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
    )
    assert device is not None

    assert (
        await get_diagnostics_for_device(hass, hass_client, entry, device) == snapshot
    )
