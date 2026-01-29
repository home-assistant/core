"""Tests for the Freebox sensors."""

from copy import deepcopy
from unittest.mock import Mock

from freebox_api.exceptions import HttpRequestError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_platform
from .const import (
    DATA_CONNECTION_GET_FTTH,
    DATA_CONNECTION_GET_STATUS,
    DATA_HOME_GET_NODES,
    DATA_STORAGE_GET_DISKS,
)

from tests.common import async_fire_time_changed


async def test_network_speed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test missed call sensor."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.freebox_download_speed").state == "198.9"
    assert hass.states.get("sensor.freebox_upload_speed").state == "1440.0"

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
    assert hass.states.get("sensor.freebox_download_speed").state == "123.4"
    assert hass.states.get("sensor.freebox_upload_speed").state == "432.1"


async def test_ftth_power(hass: HomeAssistant, router: Mock) -> None:
    """Test FTTH optical power sensors."""
    await setup_platform(hass, SENSOR_DOMAIN)

    state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    state_tx = hass.states.get("sensor.freebox_sfp_tx_power")

    assert state_rx.state == "-22.25"
    assert state_tx.state == "-3.66"
    assert state_rx.attributes["unit_of_measurement"] == "dBm"
    assert state_tx.attributes["unit_of_measurement"] == "dBm"


async def test_ftth_api_error(hass: HomeAssistant, router: Mock) -> None:
    """Test FTTH sensors when API call fails."""
    router().connection.get_ftth.side_effect = HttpRequestError("Connection failed")
    await setup_platform(hass, SENSOR_DOMAIN)

    # FTTH sensors should not be created when API fails
    assert hass.states.get("sensor.freebox_sfp_rx_power") is None
    assert hass.states.get("sensor.freebox_sfp_tx_power") is None


async def test_ftth_power_conversion(hass: HomeAssistant, router: Mock) -> None:
    """Test FTTH optical power conversion from centidBm to dBm."""
    # Mock API response with different power values (in centidBm)
    ftth_data = deepcopy(DATA_CONNECTION_GET_FTTH)
    ftth_data["sfp_pwr_rx"] = -1500  # -15.00 dBm
    ftth_data["sfp_pwr_tx"] = -250  # -2.50 dBm
    router().connection.get_ftth.return_value = ftth_data

    await setup_platform(hass, SENSOR_DOMAIN)

    state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    state_tx = hass.states.get("sensor.freebox_sfp_tx_power")

    assert state_rx.state == "-15.0"  # Converted from -1500 centidBm
    assert state_tx.state == "-2.5"  # Converted from -250 centidBm


async def test_no_ftth_media(hass: HomeAssistant, router: Mock) -> None:
    """Test that FTTH sensors are not created when media is not FTTH."""
    data_connection_get_status = deepcopy(DATA_CONNECTION_GET_STATUS)
    data_connection_get_status["media"] = "dsl"
    router().connection.get_status.return_value = data_connection_get_status
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.freebox_sfp_rx_power") is None
    assert hass.states.get("sensor.freebox_sfp_tx_power") is None


async def test_call(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test missed call sensor."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.freebox_missed_calls").state == "3"

    # Simulate we marked calls as read
    data_call_get_calls_marked_as_read = []
    router().call.get_calls_log.return_value = data_call_get_calls_marked_as_read
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.freebox_missed_calls").state == "0"


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

    assert hass.states.get("sensor.freebox_free_space").state == "88.27"

    # Simulate a changed storage size
    data_storage_get_disks_changed = deepcopy(DATA_STORAGE_GET_DISKS)
    data_storage_get_disks_changed[2]["partitions"][0]["free_bytes"] = 880000000000
    router().storage.get_disks.return_value = data_storage_get_disks_changed
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()
    assert hass.states.get("sensor.freebox_free_space").state == "44.9"


async def test_battery(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test battery sensor."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.telecommande_niveau_de_batterie").state == "100"
    assert hass.states.get("sensor.ouverture_porte_niveau_de_batterie").state == "100"
    assert hass.states.get("sensor.detecteur_niveau_de_batterie").state == "100"

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
    assert hass.states.get("sensor.telecommande_niveau_de_batterie").state == "25"
    assert hass.states.get("sensor.ouverture_porte_niveau_de_batterie").state == "50"
    assert hass.states.get("sensor.detecteur_niveau_de_batterie").state == "75"
