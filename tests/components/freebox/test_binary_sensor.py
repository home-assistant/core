"""Tests for the Freebox binary sensors."""

import asyncio
from copy import deepcopy
from typing import Any
from unittest.mock import Mock

from freebox_api.exceptions import AuthorizationError, HttpRequestError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .common import setup_platform
from .const import (
    DATA_HOME_PIR_GET_VALUE,
    DATA_STORAGE_GET_RAIDS,
    DATA_SWITCH_GET_STATUS,
)


async def test_raid_array_degraded(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test raid array degraded binary sensor."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    assert (
        hass.states.get("binary_sensor.freebox_server_r2_raid_array_0_degraded").state
        == "off"
    )

    # Now simulate we degraded
    data_storage_get_raids_degraded = deepcopy(DATA_STORAGE_GET_RAIDS)
    data_storage_get_raids_degraded[0]["degraded"] = True
    router().storage.get_raids.return_value = data_storage_get_raids_degraded
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.freebox_server_r2_raid_array_0_degraded").state
        == "on"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_home(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test home binary sensors."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    # Device class
    assert (
        hass.states.get("binary_sensor.detecteur").attributes[ATTR_DEVICE_CLASS]
        == BinarySensorDeviceClass.MOTION
    )
    assert (
        hass.states.get("binary_sensor.ouverture_porte").attributes[ATTR_DEVICE_CLASS]
        == BinarySensorDeviceClass.DOOR
    )
    assert (
        hass.states.get("binary_sensor.ouverture_porte_cover").attributes[
            ATTR_DEVICE_CLASS
        ]
        == BinarySensorDeviceClass.SAFETY
    )

    # Initial state
    assert hass.states.get("binary_sensor.detecteur").state == "on"
    assert hass.states.get("binary_sensor.detecteur_cover").state == "off"
    # Each sensor is read once when added
    assert hass.states.get("binary_sensor.ouverture_porte").state == "on"
    assert hass.states.get("binary_sensor.ouverture_porte_cover").state == "off"

    # Now simulate a changed status
    data_home_get_values_changed = deepcopy(DATA_HOME_PIR_GET_VALUE)
    data_home_get_values_changed["value"] = True
    router().home.get_home_endpoint_value.return_value = data_home_get_values_changed

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.detecteur").state == "off"
    assert hass.states.get("binary_sensor.detecteur_cover").state == "on"
    assert hass.states.get("binary_sensor.ouverture_porte").state == "off"
    assert hass.states.get("binary_sensor.ouverture_porte_cover").state == "on"


async def _update_entity(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "homeassistant", "update_entity", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


@pytest.mark.parametrize(
    ("entity_id", "initial_state"),
    [
        ("binary_sensor.detecteur", "on"),
        ("binary_sensor.ouverture_porte", "on"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_entity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    router: Mock,
    entity_id: str,
    initial_state: str,
) -> None:
    """Test the motion and door sensors are read on request, and only then."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)
    assert await async_setup_component(hass, "homeassistant", {})
    assert hass.states.get(entity_id).state == initial_state

    data_home_get_values_changed = deepcopy(DATA_HOME_PIR_GET_VALUE)
    data_home_get_values_changed["value"] = True
    read = router().home.get_home_endpoint_value
    read.return_value = data_home_get_values_changed
    read.reset_mock()

    read.return_value = DATA_HOME_PIR_GET_VALUE
    await _update_entity(hass, entity_id)
    assert read.call_count == 1
    assert hass.states.get(entity_id).state == "on"
    read.return_value = data_home_get_values_changed
    await _update_entity(hass, entity_id)
    assert hass.states.get(entity_id).state == "off"
    endpoint = read.call_args.args

    # No polling on top of the router update: this sensor is read once every 30 s
    read.reset_mock()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [call.args for call in read.call_args_list].count(endpoint) == 1

    # A failed read keeps the last known state
    for error in (HttpRequestError("failed"), AuthorizationError("failed")):
        read.side_effect = error
        await _update_entity(hass, entity_id)
        assert hass.states.get(entity_id).state == "off"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_reads_do_not_overlap(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test a slow read on request blocks the router update of the same sensor."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)
    assert await async_setup_component(hass, "homeassistant", {})

    data_home_get_values_changed = deepcopy(DATA_HOME_PIR_GET_VALUE)
    data_home_get_values_changed["value"] = True
    release = asyncio.Event()
    running = set()
    overlapped = False

    async def slow_read(*endpoint: int) -> dict[str, Any]:
        nonlocal overlapped
        overlapped |= endpoint in running
        running.add(endpoint)
        await release.wait()
        running.discard(endpoint)
        return data_home_get_values_changed

    read = router().home.get_home_endpoint_value
    read.reset_mock()
    read.side_effect = slow_read

    request = hass.async_create_task(_update_entity(hass, "binary_sensor.detecteur"))
    for _ in range(10):
        await asyncio.sleep(0)
    assert read.call_count == 1
    motion_endpoint = read.call_args.args

    # The router update waits for the running read
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    for _ in range(10):
        await asyncio.sleep(0)

    release.set()
    await request
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not overlapped
    assert [call.args for call in read.call_args_list].count(motion_endpoint) == 2
    assert hass.states.get("binary_sensor.detecteur").state == "off"


@pytest.mark.usefixtures("router")
async def test_home_node_firmware_version(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the firmware version of a home node is passed as a string."""
    entry = await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    # The PIR detector from the fixture reports its firmware version as a number
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, 26), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "29871925"
    assert "non-string value" not in caplog.text


async def test_lan_port_link(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test LAN port link binary sensors."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    state = hass.states.get("binary_sensor.freebox_server_r2_ethernet_1_link")
    assert state.state == "on"
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY
    assert (
        hass.states.get("binary_sensor.freebox_server_r2_sfp_lan_link").state == "off"
    )

    # Simulate the port being unplugged
    data_switch_get_status_changed = deepcopy(DATA_SWITCH_GET_STATUS)
    data_switch_get_status_changed[0]["link"] = "down"
    router().switch.get_status.return_value = data_switch_get_status_changed
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.freebox_server_r2_ethernet_1_link").state
        == "off"
    )
