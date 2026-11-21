"""Test Awair init."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.awair.const import DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, discovery_flow, frame

from . import setup_awair
from .const import LOCAL_CONFIG, LOCAL_UNIQUE_ID, ZEROCONF_DISCOVERY

DISCOVERY_KEY = discovery_flow.DiscoveryKey(
    domain="zeroconf",
    key=("_http._tcp.local.", "awair12345._http._tcp.local."),
    version=1,
)


async def test_local_awair_sensors(
    hass: HomeAssistant, local_devices, local_data, device_registry: dr.DeviceRegistry
) -> None:
    """Test expected sensors on a local Awair."""
    fixtures = [local_devices, local_data]
    entry = await setup_awair(hass, fixtures, LOCAL_UNIQUE_ID, LOCAL_CONFIG)

    device_entry = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    assert device_entry.name == "Mock Title"

    with patch("python_awair.AwairClient.query", side_effect=fixtures):
        hass.config_entries.async_update_entry(entry, title="Hello World")
        await hass.async_block_till_done()

    device_entry = device_registry.async_get(device_entry.id)
    assert device_entry.name == "Hello World"


async def test_zeroconf_host_change_reloads_local_entry(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    local_devices: Any,
    local_data: Any,
) -> None:
    """Test zeroconf discovery of a new host reloads a loaded local entry once."""
    entry = await setup_awair(
        hass, [local_devices, local_data], LOCAL_UNIQUE_ID, {CONF_HOST: "127.0.0.1"}
    )
    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data

    with (
        patch(
            "python_awair.AwairClient.query",
            side_effect=[local_devices, local_devices, local_data],
        ) as mock_query,
        patch.object(frame, "_REPORTED_INTEGRATIONS", set()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF, "discovery_key": DISCOVERY_KEY},
            data=ZEROCONF_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_device"
    assert entry.data[CONF_HOST] == ZEROCONF_DISCOVERY.host
    assert entry.discovery_keys == {"zeroconf": (DISCOVERY_KEY,)}
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not coordinator
    assert mock_query.call_count == 3
    assert "has an update listener" not in caplog.text
