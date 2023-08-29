"""Tests for the Freebox sensors."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

from homeassistant.components.freebox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .const import (
    DATA_CONNECTION_GET_STATUS,
    DATA_HOME_GET_NODES,
    DATA_STORAGE_GET_DISKS,
    MOCK_HOST,
    MOCK_PORT,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_network_speed(hass: HomeAssistant, router: Mock) -> None:
    """Test missed call sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.freebox_download_speed").state == "198.9"
    assert hass.states.get("sensor.freebox_upload_speed").state == "1440.0"

    # Simulate a changed speed
    data_connection_get_status_changed = deepcopy(DATA_CONNECTION_GET_STATUS)
    data_connection_get_status_changed["rate_down"] = 123400
    data_connection_get_status_changed["rate_up"] = 432100
    router().connection.get_status.return_value = data_connection_get_status_changed
    # Simulate an update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.freebox_download_speed").state == "123.4"
    assert hass.states.get("sensor.freebox_upload_speed").state == "432.1"


async def test_call(hass: HomeAssistant, router: Mock) -> None:
    """Test missed call sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.freebox_missed_calls").state == "3"

    # Simulate we marked calls as read
    data_call_get_calls_marked_as_read = []
    router().call.get_calls_log.return_value = data_call_get_calls_marked_as_read
    # Simulate an update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.freebox_missed_calls").state == "0"


async def test_disk(hass: HomeAssistant, router: Mock) -> None:
    """Test disk sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.freebox_free_space").state == "88.27"

    # Simulate a changed storage size
    data_storage_get_disks_changed = deepcopy(DATA_STORAGE_GET_DISKS)
    data_storage_get_disks_changed[2]["partitions"][0]["free_bytes"] = 880000000000
    router().storage.get_disks.return_value = data_storage_get_disks_changed
    # Simulate an update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.freebox_free_space").state == "44.9"


async def test_battery(hass: HomeAssistant, router: Mock) -> None:
    """Test battery sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.telecommande_niveau_de_batterie").state == "100"
    assert hass.states.get("sensor.ouverture_porte_niveau_de_batterie").state == "100"
    assert hass.states.get("sensor.detecteur_niveau_de_batterie").state == "100"

    # Simulate a changed battery
    data_home_get_nodes_changed = deepcopy(DATA_HOME_GET_NODES)
    data_home_get_nodes_changed[2]["show_endpoints"][3]["value"] = 25
    data_home_get_nodes_changed[3]["show_endpoints"][3]["value"] = 50
    data_home_get_nodes_changed[4]["show_endpoints"][3]["value"] = 75
    router().home.get_home_nodes.return_value = data_home_get_nodes_changed
    # Simulate an update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.telecommande_niveau_de_batterie").state == "25"
    assert hass.states.get("sensor.ouverture_porte_niveau_de_batterie").state == "50"
    assert hass.states.get("sensor.detecteur_niveau_de_batterie").state == "75"
