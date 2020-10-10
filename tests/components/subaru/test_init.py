"""Test Subaru init process."""
from datetime import datetime, timedelta

from subarulink import InvalidCredentials, SubaruException

from homeassistant.components import subaru
from homeassistant.components.subaru.const import (
    CONF_HARD_POLL_INTERVAL,
    DEFAULT_HARD_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_CONTROLLER,
    ENTRY_COORDINATOR,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_SERVICE,
    VEHICLE_HAS_REMOTE_START,
    VEHICLE_HAS_SAFETY_SERVICE,
    VEHICLE_NAME,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.setup import async_setup_component

from .api_responses import (
    TEST_VIN_1_G1,
    TEST_VIN_2_EV,
    TEST_VIN_3_G2,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
    VEHICLE_STATUS_G2,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_setup_with_no_config(hass):
    """Test DOMAIN is empty if there is no config."""
    assert await async_setup_component(hass, DOMAIN, {}) is True
    assert DOMAIN in hass.data
    assert hass.data[DOMAIN] == {}


async def test_setup_ev(hass):
    """Test setup with an EV vehicle."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
    assert hass.data[DOMAIN][entry.entry_id]


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


async def test_update_failed(hass):
    """Tests when coordinator update fails."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
    coordinator = hass.data[DOMAIN][entry.entry_id][ENTRY_COORDINATOR]

    with patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.fetch",
        side_effect=SubaruException("403 Error"),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        odometer = hass.states.get("sensor.test_vehicle_2_odometer")
        assert odometer.state == "unavailable"


async def test_update_listener(hass):
    """Test config options update listener."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
    assert hass.data[DOMAIN][entry.entry_id]

    coordinator = hass.data[DOMAIN][entry.entry_id][ENTRY_COORDINATOR]
    controller = hass.data[DOMAIN][entry.entry_id][ENTRY_CONTROLLER]
    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)
    assert controller.get_update_interval() == DEFAULT_HARD_POLL_INTERVAL

    result = await hass.config_entries.options.async_init(entry.entry_id)
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


async def test_unload_entry(hass):
    """Test that entry is unloaded."""
    entry = await setup_subaru_integration(
        hass, vehicle_list=[TEST_VIN_2_EV], vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV]
    )
    assert hass.data[DOMAIN][entry.entry_id]

    assert await subaru.async_unload_entry(hass, entry)
    assert DOMAIN in hass.data
    assert hass.data[DOMAIN] == {}


TEST_CONFIG = {
    CONF_USERNAME: "user",
    CONF_PASSWORD: "password",
    CONF_PIN: "1234",
    CONF_DEVICE_ID: int(datetime.now().timestamp()),
}

TEST_OPTIONS = {
    CONF_HARD_POLL_INTERVAL: DEFAULT_HARD_POLL_INTERVAL,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}


async def setup_subaru_integration(
    hass,
    vehicle_list=None,
    vehicle_data=None,
    vehicle_status=None,
    connect_success=True,
):
    """Create Subaru entry."""
    assert await async_setup_component(hass, DOMAIN, {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
        options=TEST_OPTIONS,
        entry_id=1,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.connect",
        return_value=connect_success,
        side_effect=None
        if connect_success
        else InvalidCredentials("Invalid Credentials"),
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_vehicles",
        return_value=vehicle_list,
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.vin_to_name",
        return_value=vehicle_data[VEHICLE_NAME],
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_api_gen",
        return_value=vehicle_data[VEHICLE_API_GEN],
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_ev_status",
        return_value=vehicle_data[VEHICLE_HAS_EV],
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_res_status",
        return_value=vehicle_data[VEHICLE_HAS_REMOTE_START],
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_remote_status",
        return_value=vehicle_data[VEHICLE_HAS_REMOTE_SERVICE],
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_safety_status",
        return_value=vehicle_data[VEHICLE_HAS_SAFETY_SERVICE],
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_data",
        return_value=vehicle_status,
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.update",
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.fetch",
    ):
        success = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    if success:
        return config_entry
    return None
