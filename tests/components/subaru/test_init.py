"""Test Subaru component setup and updates."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components import subaru
from homeassistant.components.subaru.const import (
    CONF_HARD_POLL_INTERVAL,
    DEFAULT_HARD_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_CONTROLLER,
    ENTRY_COORDINATOR,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.setup import async_setup_component
from subarulink import SubaruException

from .api_responses import (
    TEST_VIN_1_G1,
    TEST_VIN_2_EV,
    TEST_VIN_3_G2,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
    VEHICLE_STATUS_G2,
)
from .conftest import setup_subaru_integration


async def test_setup_with_no_config(hass):
    """Test DOMAIN is empty if there is no config."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert DOMAIN in hass.data
    assert hass.data[DOMAIN] == {}


async def test_setup_ev(hass, ev_entry):
    """Test setup with an EV vehicle."""
    assert hass.data[DOMAIN][ev_entry.entry_id]


async def test_setup_g2(hass):
    """Test setup with a G2 vehcile ."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_3_G2],
        vehicle_data=VEHICLE_DATA[TEST_VIN_3_G2],
        vehicle_status=VEHICLE_STATUS_G2,
    )
    assert hass.data[DOMAIN][entry.entry_id]


async def test_setup_g1(hass):
    """Test setup with a G1 vehicle."""
    entry = await setup_subaru_integration(
        hass, vehicle_list=[TEST_VIN_1_G1], vehicle_data=VEHICLE_DATA[TEST_VIN_1_G1]
    )
    assert hass.data[DOMAIN][entry.entry_id]


async def test_unsuccessful_connect(hass):
    """Test that entry is not loaded after unsuccessful connection."""
    await setup_subaru_integration(
        hass,
        connect_success=False,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert hass.data[DOMAIN] == {}


async def test_update_failed(hass, ev_entry):
    """Tests when coordinator update fails."""
    coordinator = hass.data[DOMAIN][ev_entry.entry_id][ENTRY_COORDINATOR]

    with patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.fetch",
        side_effect=SubaruException("403 Error"),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        odometer = hass.states.get("sensor.test_vehicle_2_odometer")
        assert odometer.state == "unavailable"


async def test_update_listener(hass, ev_entry):
    """Test config options update listener."""
    coordinator = hass.data[DOMAIN][ev_entry.entry_id][ENTRY_COORDINATOR]
    controller = hass.data[DOMAIN][ev_entry.entry_id][ENTRY_CONTROLLER]
    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)
    assert controller.get_update_interval() == DEFAULT_HARD_POLL_INTERVAL

    result = await hass.config_entries.options.async_init(ev_entry.entry_id)
    new_scan_interval = 240
    new_hard_poll_interval = 720
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: new_scan_interval,
            CONF_HARD_POLL_INTERVAL: new_hard_poll_interval,
        },
    )
    await hass.async_block_till_done()

    assert coordinator.update_interval == timedelta(seconds=new_scan_interval)
    assert controller.get_update_interval() == new_hard_poll_interval


async def test_unload_entry(hass, ev_entry):
    """Test that entry is unloaded."""
    assert await subaru.async_unload_entry(hass, ev_entry)
    assert DOMAIN in hass.data
    assert hass.data[DOMAIN] == {}
