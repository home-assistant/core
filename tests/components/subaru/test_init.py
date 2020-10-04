"""Test Subaru init process."""
from datetime import datetime, timedelta

from subarulink import InvalidCredentials

from homeassistant.components import subaru
from homeassistant.components.subaru.const import (
    CONF_HARD_POLL_INTERVAL,
    DEFAULT_HARD_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_CONTROLLER,
    ENTRY_COORDINATOR,
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
    """Test DOMAIN does not exist if there is no config."""
    assert await async_setup_component(hass, DOMAIN, {}) is True
    assert DOMAIN not in hass.data


async def test_setup_EV(hass):
    """Test setup with an EV vehicle."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
    assert hass.data[DOMAIN][entry.entry_id]


async def test_setup_G2(hass):
    """Test setup with a G2 vehcile ."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_3_G2],
        vehicle_data=VEHICLE_DATA[TEST_VIN_3_G2],
        vehicle_status=VEHICLE_STATUS_G2,
    )
    assert hass.data[DOMAIN][entry.entry_id]


async def test_setup_G1(hass):
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

    assert DOMAIN not in hass.data


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
    NEW_SCAN_INTERVAL = 240
    NEW_HARD_POLL_INTERVAL = 720
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: NEW_SCAN_INTERVAL,
            CONF_HARD_POLL_INTERVAL: NEW_HARD_POLL_INTERVAL,
        },
    )
    await hass.async_block_till_done()

    assert coordinator.update_interval == timedelta(seconds=NEW_SCAN_INTERVAL)
    assert controller.get_update_interval() == NEW_HARD_POLL_INTERVAL


async def test_unload_entry(hass):
    """Test that entry is unloaded."""
    entry = await setup_subaru_integration(
        hass, vehicle_list=[TEST_VIN_2_EV], vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV]
    )
    assert hass.data[DOMAIN][entry.entry_id]

    assert await subaru.async_unload_entry(hass, entry)
    assert DOMAIN not in hass.data


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
    config=TEST_CONFIG,
    options=TEST_OPTIONS,
    vehicle_list=None,
    vehicle_data=None,
    vehicle_status=None,
    connect_success=True,
):
    """Create Subaru entry."""
    assert await async_setup_component(hass, DOMAIN, {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        options=options,
        entry_id=1,
    )
    config_entry.add_to_hass(hass)

    connect_effect = None
    if not connect_success:
        connect_effect = InvalidCredentials("Invalid Credentials")

    with patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.connect",
        return_value=connect_success,
        side_effect=connect_effect,
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_vehicles",
        return_value=vehicle_list,
    ), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.vin_to_name",
        return_value=vehicle_data[VEHICLE_NAME],
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
    ):
        success = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    if success:
        return config_entry
    return None
