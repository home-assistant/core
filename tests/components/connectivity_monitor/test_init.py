"""Tests for Connectivity Monitor initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock, call, patch

from homeassistant.components.connectivity_monitor import async_migrate_entry
from homeassistant.components.connectivity_monitor.const import (
    CONF_DNS_SERVER,
    CONF_HOST,
    CONF_INTERVAL,
    CONF_PROTOCOL,
    CONF_TARGETS,
    CONF_ZHA_IEEE,
    DEFAULT_DNS_SERVER,
    DOMAIN,
    PROTOCOL_ICMP,
    PROTOCOL_MATTER,
    PROTOCOL_ZHA,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    network_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.connectivity_monitor.sensor."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.sensor."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": True,
                    "latency": 3.2,
                    "resolved_ip": "192.168.1.1",
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(network_config_entry.entry_id)
        await hass.async_block_till_done()

    assert network_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.connectivity_monitor_router_icmp") is not None

    alert_handler = hass.data[DOMAIN][network_config_entry.entry_id]["alert_handler"]
    alert_handler.async_cleanup = AsyncMock()

    assert await hass.config_entries.async_unload(network_config_entry.entry_id)
    await hass.async_block_till_done()

    assert alert_handler.async_cleanup.await_count == 1
    assert network_config_entry.state is ConfigEntryState.NOT_LOADED
    assert network_config_entry.entry_id not in hass.data[DOMAIN]


async def test_migrate_entry_splits_legacy_targets(hass: HomeAssistant) -> None:
    """Test legacy v1 entries are migrated into typed entries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Connectivity Monitor",
        version=1,
        data={
            CONF_TARGETS: [
                {
                    CONF_HOST: "192.168.1.10",
                    CONF_PROTOCOL: PROTOCOL_ICMP,
                    "device_name": "Router",
                },
                {
                    CONF_PROTOCOL: PROTOCOL_ZHA,
                    CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                    CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                    "device_name": "Door Sensor",
                },
                {
                    CONF_PROTOCOL: PROTOCOL_MATTER,
                    CONF_HOST: "matter:1-1234",
                    "matter_node_id": "1-1234",
                    "device_name": "Thermostat",
                },
            ],
            CONF_INTERVAL: 120,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries.flow,
        "async_init",
        AsyncMock(return_value={"type": "create_entry"}),
    ) as mock_async_init:
        assert await async_migrate_entry(hass, config_entry)
        await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.title == "Network Monitor"
    assert config_entry.unique_id == "connectivity_monitor_network"
    assert config_entry.data == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.10",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Router",
            }
        ],
        CONF_INTERVAL: 120,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }
    assert mock_async_init.await_args_list == [
        call(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_TARGETS: [
                    {
                        CONF_PROTOCOL: PROTOCOL_ZHA,
                        CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                        CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                        "device_name": "Door Sensor",
                    }
                ],
                CONF_INTERVAL: 120,
                CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
                "entry_type": "zha",
            },
        ),
        call(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_TARGETS: [
                    {
                        CONF_PROTOCOL: PROTOCOL_MATTER,
                        CONF_HOST: "matter:1-1234",
                        "matter_node_id": "1-1234",
                        "device_name": "Thermostat",
                    }
                ],
                CONF_INTERVAL: 120,
                CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
                "entry_type": "matter",
            },
        ),
    ]
