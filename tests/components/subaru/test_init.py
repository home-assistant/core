"""Test Subaru component setup and updates."""
from datetime import timedelta
from unittest.mock import patch

from subarulink import SubaruException

from homeassistant.components.subaru.const import (
    CONF_HARD_POLL_INTERVAL,
    DEFAULT_HARD_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_CONTROLLER,
    ENTRY_COORDINATOR,
    REMOTE_SERVICE_FETCH,
    VEHICLE_VIN,
)
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.setup import async_setup_component

from .api_responses import (
    TEST_VIN_1_G1,
    TEST_VIN_2_EV,
    TEST_VIN_3_G2,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
    VEHICLE_STATUS_G2,
)
from .conftest import (
    MOCK_API_CONNECT,
    MOCK_API_FETCH,
    MOCK_API_GET_GET_DATA,
    setup_subaru_integration,
)


async def test_setup_with_no_config(hass):
    """Test DOMAIN is empty if there is no config."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert DOMAIN not in hass.config_entries.async_domains()


async def test_setup_ev(hass, ev_entry):
    """Test setup with an EV vehicle."""
    check_entry = hass.config_entries.async_get_entry(ev_entry.entry_id)
    assert check_entry
    assert check_entry.state == ENTRY_STATE_LOADED


async def test_setup_g2(hass):
    """Test setup with a G2 vehcile ."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_3_G2],
        vehicle_data=VEHICLE_DATA[TEST_VIN_3_G2],
        vehicle_status=VEHICLE_STATUS_G2,
    )
    check_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert check_entry
    assert check_entry.state == ENTRY_STATE_LOADED


async def test_setup_g1(hass):
    """Test setup with a G1 vehicle."""
    entry = await setup_subaru_integration(
        hass, vehicle_list=[TEST_VIN_1_G1], vehicle_data=VEHICLE_DATA[TEST_VIN_1_G1]
    )
    check_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert check_entry
    assert check_entry.state == ENTRY_STATE_LOADED


async def test_unsuccessful_connect(hass):
    """Test that entry is not loaded after unsuccessful connection."""
    entry = await setup_subaru_integration(
        hass,
        connect_success=False,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
    check_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert check_entry
    assert check_entry.state == ENTRY_STATE_SETUP_RETRY


async def test_update_failed(hass, ev_entry):
    """Tests when coordinator update fails."""
    with patch(
        MOCK_API_FETCH,
        side_effect=SubaruException("403 Error"),
    ):
        await hass.services.async_call(
            DOMAIN,
            REMOTE_SERVICE_FETCH,
            {VEHICLE_VIN: TEST_VIN_2_EV},
            blocking=True,
        )
        await hass.helpers.entity_component.async_update_entity(
            "sensor.test_vehicle_2_odometer"
        )
        await hass.async_block_till_done()

        odometer = hass.states.get("sensor.test_vehicle_2_odometer")
        assert odometer.state == "unavailable"


async def test_fetch_service_invalid_vin(hass, ev_entry):
    """Tests fetch service called with an invalid VIN."""
    with patch(MOCK_API_CONNECT) as mock_fetch, patch(
        MOCK_API_GET_GET_DATA
    ) as mock_get_data:
        await hass.services.async_call(
            DOMAIN,
            REMOTE_SERVICE_FETCH,
            {VEHICLE_VIN: "ABC123"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_fetch.assert_not_called()
        mock_get_data.assert_not_called()


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
    assert ev_entry.state == ENTRY_STATE_LOADED
    assert await hass.config_entries.async_unload(ev_entry.entry_id)
    await hass.async_block_till_done()
    assert ev_entry.state == ENTRY_STATE_NOT_LOADED
