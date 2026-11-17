"""Tests for the Freebox sensors."""

from copy import deepcopy
from typing import Any
from unittest.mock import Mock, call

from freebox_api.exceptions import HttpRequestError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform
from .const import (
    DATA_CONNECTION_GET_STATUS,
    DATA_HOME_GET_NODES,
    DATA_STORAGE_GET_DISKS,
    DATA_SWITCH_GET_PORT_STATS,
    DATA_SWITCH_GET_STATUS,
)

ETHERNET_1_RECEIVE_RATE = "sensor.freebox_server_r2_ethernet_1_receive_rate"
ETHERNET_1_TRANSMIT_RATE = "sensor.freebox_server_r2_ethernet_1_transmit_rate"


@pytest.mark.usefixtures("router", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor entities."""
    entry = await setup_platform(hass, SENSOR_DOMAIN)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_network_speed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test missed call sensor."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.freebox_server_r2_download_speed").state == "198.9"
    assert hass.states.get("sensor.freebox_server_r2_upload_speed").state == "1440.0"

    # Simulate a changed speed
    data_connection_get_status_changed = deepcopy(DATA_CONNECTION_GET_STATUS)
    data_connection_get_status_changed["rate_down"] = 123400
    data_connection_get_status_changed["rate_up"] = 432100
    router().connection.get_status.return_value = data_connection_get_status_changed
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.freebox_server_r2_download_speed").state == "123.4"
    assert hass.states.get("sensor.freebox_server_r2_upload_speed").state == "432.1"


async def test_connection_down(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test IP sensors become unknown when the API stops returning them."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.freebox_server_r2_connection_state").state == "up"

    data_connection_down = deepcopy(DATA_CONNECTION_GET_STATUS)
    data_connection_down["state"] = "down"
    del data_connection_down["ipv4"]
    del data_connection_down["ipv6"]
    router().connection.get_status.return_value = data_connection_down
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()

    assert hass.states.get("sensor.freebox_server_r2_connection_state").state == "down"
    assert (
        hass.states.get("sensor.freebox_server_r2_wan_ipv4_address").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.freebox_server_r2_wan_ipv6_address").state
        == STATE_UNKNOWN
    )


async def test_call(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test missed call sensor."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.freebox_server_r2_missed_calls").state == "3"

    # Simulate we marked calls as read
    data_call_get_calls_marked_as_read = []
    router().call.get_calls_log.return_value = data_call_get_calls_marked_as_read
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.freebox_server_r2_missed_calls").state == "0"


async def test_disk(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test disk sensor."""
    await setup_platform(hass, SENSOR_DOMAIN)

    # Initial state
    assert (
        router().storage.get_disks.return_value[2]["partitions"][0]["total_bytes"]
        == 1960000000000
    )

    assert (
        router().storage.get_disks.return_value[2]["partitions"][0]["free_bytes"]
        == 1730000000000
    )

    assert hass.states.get("sensor.disk_3000_freebox_free_space").state == "88.27"

    # Simulate a changed storage size
    data_storage_get_disks_changed = deepcopy(DATA_STORAGE_GET_DISKS)
    data_storage_get_disks_changed[2]["partitions"][0]["free_bytes"] = 880000000000
    router().storage.get_disks.return_value = data_storage_get_disks_changed
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.disk_3000_freebox_free_space").state == "44.9"


async def test_battery(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test battery sensor."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.telecommande_battery").state == "100"
    assert hass.states.get("sensor.ouverture_porte_battery").state == "100"
    assert hass.states.get("sensor.detecteur_battery").state == "100"

    # Simulate a changed battery
    data_home_get_nodes_changed = deepcopy(DATA_HOME_GET_NODES)
    data_home_get_nodes_changed[2]["show_endpoints"][3]["value"] = 25
    data_home_get_nodes_changed[3]["show_endpoints"][4]["value"] = 50
    data_home_get_nodes_changed[4]["show_endpoints"][5]["value"] = 75
    router().home.get_home_nodes.return_value = data_home_get_nodes_changed
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.telecommande_battery").state == "25"
    assert hass.states.get("sensor.ouverture_porte_battery").state == "50"
    assert hass.states.get("sensor.detecteur_battery").state == "75"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lan_port(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test LAN port traffic sensors."""
    await setup_platform(hass, SENSOR_DOMAIN)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ETHERNET_1_RECEIVE_RATE).state == "12.345"
    assert hass.states.get(ETHERNET_1_TRANSMIT_RATE).state == "67.89"

    # Simulate a changed rate
    data_switch_get_port_stats_changed = deepcopy(DATA_SWITCH_GET_PORT_STATS)
    data_switch_get_port_stats_changed["rx_bytes_rate"] = 1000
    router().switch.get_port_stats.return_value = data_switch_get_port_stats_changed
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ETHERNET_1_RECEIVE_RATE).state == "1.0"


async def test_lan_port_rate_disabled_by_default(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    router: Mock,
) -> None:
    """Test port stats are not fetched while the traffic sensors are disabled."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert entity_registry.async_get(ETHERNET_1_RECEIVE_RATE).disabled_by == (
        er.RegistryEntryDisabler.INTEGRATION
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    router().switch.get_port_stats.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lan_port_without_name(hass: HomeAssistant, router: Mock) -> None:
    """Test LAN port sensors fall back to the port id without a name."""
    data_switch_get_status_no_name = deepcopy(DATA_SWITCH_GET_STATUS)
    del data_switch_get_status_no_name[0]["name"]
    router().switch.get_status.return_value = data_switch_get_status_no_name
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.freebox_server_r2_port_1_receive_rate")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lan_port_stats_stop_after_removal(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    router: Mock,
) -> None:
    """Test port stats stop once both traffic sensors of the port are removed."""
    await setup_platform(hass, SENSOR_DOMAIN)

    # The transmit rate sensor still needs the stats of the port
    entity_registry.async_remove(ETHERNET_1_RECEIVE_RATE)
    await hass.async_block_till_done()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert call(1) in router().switch.get_port_stats.call_args_list

    entity_registry.async_remove(ETHERNET_1_TRANSMIT_RATE)
    await hass.async_block_till_done()
    router().switch.get_port_stats.reset_mock()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert call(1) not in router().switch.get_port_stats.call_args_list


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lan_port_stats_failure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test a failed stats request only affects its own LAN port."""

    async def get_port_stats(port_id: int) -> dict[str, Any]:
        if port_id == 1:
            raise HttpRequestError("Request failed")
        return DATA_SWITCH_GET_PORT_STATS

    router().switch.get_port_stats.side_effect = get_port_stats
    await setup_platform(hass, SENSOR_DOMAIN)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ETHERNET_1_RECEIVE_RATE).state == STATE_UNAVAILABLE
    assert (
        hass.states.get("sensor.freebox_server_r2_ethernet_2_receive_rate").state
        == "12.345"
    )

    router().switch.get_port_stats.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ETHERNET_1_RECEIVE_RATE).state == "12.345"
