"""Common functions needed to setup tests for Subaru component."""
from unittest.mock import patch

import pytest
from subarulink.const import COUNTRY_USA

from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.components.subaru.const import (
    CONF_COUNTRY,
    CONF_UPDATE_ENABLED,
    DOMAIN,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_SERVICE,
    VEHICLE_HAS_REMOTE_START,
    VEHICLE_HAS_SAFETY_SERVICE,
    VEHICLE_NAME,
)
from homeassistant.config_entries import ENTRY_STATE_LOADED
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.setup import async_setup_component

from .api_responses import TEST_VIN_2_EV, VEHICLE_DATA, VEHICLE_STATUS_EV

from tests.common import MockConfigEntry

MOCK_API = "homeassistant.components.subaru.SubaruAPI."
MOCK_API_CONNECT = f"{MOCK_API}connect"
MOCK_API_IS_PIN_REQUIRED = f"{MOCK_API}is_pin_required"
MOCK_API_TEST_PIN = f"{MOCK_API}test_pin"
MOCK_API_UPDATE_SAVED_PIN = f"{MOCK_API}update_saved_pin"
MOCK_API_GET_VEHICLES = f"{MOCK_API}get_vehicles"
MOCK_API_VIN_TO_NAME = f"{MOCK_API}vin_to_name"
MOCK_API_GET_API_GEN = f"{MOCK_API}get_api_gen"
MOCK_API_GET_EV_STATUS = f"{MOCK_API}get_ev_status"
MOCK_API_GET_RES_STATUS = f"{MOCK_API}get_res_status"
MOCK_API_GET_REMOTE_STATUS = f"{MOCK_API}get_remote_status"
MOCK_API_GET_SAFETY_STATUS = f"{MOCK_API}get_safety_status"
MOCK_API_GET_GET_DATA = f"{MOCK_API}get_data"
MOCK_API_UPDATE = f"{MOCK_API}update"
MOCK_API_FETCH = f"{MOCK_API}fetch"

TEST_USERNAME = "user@email.com"
TEST_PASSWORD = "password"
TEST_PIN = "1234"
TEST_DEVICE_ID = 1613183362
TEST_COUNTRY = COUNTRY_USA

TEST_CREDS = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_COUNTRY: TEST_COUNTRY,
}

TEST_CONFIG = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_COUNTRY: TEST_COUNTRY,
    CONF_PIN: TEST_PIN,
    CONF_DEVICE_ID: TEST_DEVICE_ID,
}

TEST_OPTIONS = {
    CONF_UPDATE_ENABLED: True,
}

TEST_ENTITY_ID = "sensor.test_vehicle_2_odometer"


async def setup_subaru_integration(
    hass,
    vehicle_list=None,
    vehicle_data=None,
    vehicle_status=None,
    connect_effect=None,
    fetch_effect=None,
):
    """Create Subaru entry."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    assert await async_setup_component(hass, DOMAIN, {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
        options=TEST_OPTIONS,
        entry_id=1,
    )
    config_entry.add_to_hass(hass)

    with patch(
        MOCK_API_CONNECT,
        return_value=connect_effect is None,
        side_effect=connect_effect,
    ), patch(MOCK_API_GET_VEHICLES, return_value=vehicle_list,), patch(
        MOCK_API_VIN_TO_NAME,
        return_value=vehicle_data[VEHICLE_NAME],
    ), patch(
        MOCK_API_GET_API_GEN,
        return_value=vehicle_data[VEHICLE_API_GEN],
    ), patch(
        MOCK_API_GET_EV_STATUS,
        return_value=vehicle_data[VEHICLE_HAS_EV],
    ), patch(
        MOCK_API_GET_RES_STATUS,
        return_value=vehicle_data[VEHICLE_HAS_REMOTE_START],
    ), patch(
        MOCK_API_GET_REMOTE_STATUS,
        return_value=vehicle_data[VEHICLE_HAS_REMOTE_SERVICE],
    ), patch(
        MOCK_API_GET_SAFETY_STATUS,
        return_value=vehicle_data[VEHICLE_HAS_SAFETY_SERVICE],
    ), patch(
        MOCK_API_GET_GET_DATA,
        return_value=vehicle_status,
    ), patch(
        MOCK_API_UPDATE,
    ), patch(
        MOCK_API_FETCH, side_effect=fetch_effect
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture
async def ev_entry(hass):
    """Create a Subaru entry representing an EV vehicle with full STARLINK subscription."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
    assert DOMAIN in hass.config_entries.async_domains()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.state == ENTRY_STATE_LOADED
    return entry
