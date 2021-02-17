"""Tests for the Tuya config flow."""
from unittest.mock import Mock, patch

import pytest
from tuyaha.devices.climate import STEP_HALVES
from tuyaha.tuyaapi import TuyaAPIException, TuyaNetException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tuya.config_flow import (
    CONF_LIST_DEVICES,
    ERROR_DEV_MULTI_TYPE,
    ERROR_DEV_NOT_CONFIG,
    ERROR_DEV_NOT_FOUND,
    RESULT_AUTH_FAILED,
    RESULT_CONN_ERROR,
    RESULT_SINGLE_INSTANCE,
)
from homeassistant.components.tuya.const import (
    CONF_BRIGHTNESS_RANGE_MODE,
    CONF_COUNTRYCODE,
    CONF_CURR_TEMP_DIVIDER,
    CONF_DISCOVERY_INTERVAL,
    CONF_MAX_KELVIN,
    CONF_MAX_TEMP,
    CONF_MIN_KELVIN,
    CONF_MIN_TEMP,
    CONF_QUERY_DEVICE,
    CONF_QUERY_INTERVAL,
    CONF_SET_TEMP_DIVIDED,
    CONF_SUPPORT_COLOR,
    CONF_TEMP_DIVIDER,
    CONF_TEMP_STEP_OVERRIDE,
    CONF_TUYA_MAX_COLTEMP,
    DOMAIN,
    TUYA_DATA,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    TEMP_CELSIUS,
)

from .common import CLIMATE_ID, LIGHT_ID, LIGHT_ID_FAKE1, LIGHT_ID_FAKE2, MockTuya

from tests.common import MockConfigEntry

USERNAME = "myUsername"
PASSWORD = "myPassword"
COUNTRY_CODE = "1"
TUYA_PLATFORM = "tuya"

TUYA_USER_DATA = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_COUNTRYCODE: COUNTRY_CODE,
    CONF_PLATFORM: TUYA_PLATFORM,
}


@pytest.fixture(name="tuya")
def tuya_fixture() -> Mock:
    """Patch libraries."""
    with patch("homeassistant.components.tuya.config_flow.TuyaApi") as tuya:
        yield tuya


@pytest.fixture(name="tuya_setup", autouse=True)
def tuya_setup_fixture():
    """Mock tuya entry setup."""
    with patch("homeassistant.components.tuya.async_setup_entry", return_value=True):
        yield


async def test_user(hass, tuya):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TUYA_USER_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_COUNTRYCODE] == COUNTRY_CODE
    assert result["data"][CONF_PLATFORM] == TUYA_PLATFORM
    assert not result["result"].unique_id


async def test_import(hass, tuya):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=TUYA_USER_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_COUNTRYCODE] == COUNTRY_CODE
    assert result["data"][CONF_PLATFORM] == TUYA_PLATFORM
    assert not result["result"].unique_id


async def test_abort_if_already_setup(hass, tuya):
    """Test we abort if Tuya is already setup."""
    MockConfigEntry(domain=DOMAIN, data=TUYA_USER_DATA).add_to_hass(hass)

    # Should fail, config exist (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == RESULT_SINGLE_INSTANCE

    # Should fail, config exist (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == RESULT_SINGLE_INSTANCE


async def test_abort_on_invalid_credentials(hass, tuya):
    """Test when we have invalid credentials."""
    tuya().init.side_effect = TuyaAPIException("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": RESULT_AUTH_FAILED}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == RESULT_AUTH_FAILED


async def test_abort_on_connection_error(hass, tuya):
    """Test when we have a network error."""
    tuya().init.side_effect = TuyaNetException("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == RESULT_CONN_ERROR

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == RESULT_CONN_ERROR


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TUYA_USER_DATA,
    )
    config_entry.add_to_hass(hass)

    # Set up the integration to make sure the config flow module is loaded.
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Unload the integration to prepare for the test.
    with patch("homeassistant.components.tuya.async_unload_entry", return_value=True):
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    # Test check for integration not loaded
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == RESULT_CONN_ERROR

    # Load integration and enter options
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    hass.data[DOMAIN] = {TUYA_DATA: MockTuya()}
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # Test dev not found error
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LIST_DEVICES: [f"light-{LIGHT_ID_FAKE1}"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": ERROR_DEV_NOT_FOUND}

    # Test dev type error
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LIST_DEVICES: [f"light-{LIGHT_ID_FAKE2}"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": ERROR_DEV_NOT_CONFIG}

    # Test multi dev error
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LIST_DEVICES: [f"climate-{CLIMATE_ID}", f"light-{LIGHT_ID}"]},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": ERROR_DEV_MULTI_TYPE}

    # Test climate options form
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_LIST_DEVICES: [f"climate-{CLIMATE_ID}"]}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            CONF_TEMP_DIVIDER: 10,
            CONF_CURR_TEMP_DIVIDER: 5,
            CONF_SET_TEMP_DIVIDED: False,
            CONF_TEMP_STEP_OVERRIDE: STEP_HALVES,
            CONF_MIN_TEMP: 12,
            CONF_MAX_TEMP: 22,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # Test light options form
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_LIST_DEVICES: [f"light-{LIGHT_ID}"]}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SUPPORT_COLOR: True,
            CONF_BRIGHTNESS_RANGE_MODE: 1,
            CONF_MIN_KELVIN: 4000,
            CONF_MAX_KELVIN: 5000,
            CONF_TUYA_MAX_COLTEMP: 12000,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # Test common options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DISCOVERY_INTERVAL: 100,
            CONF_QUERY_INTERVAL: 50,
            CONF_QUERY_DEVICE: LIGHT_ID,
        },
    )

    # Verify results
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    climate_options = config_entry.options[CLIMATE_ID]
    assert climate_options[CONF_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert climate_options[CONF_TEMP_DIVIDER] == 10
    assert climate_options[CONF_CURR_TEMP_DIVIDER] == 5
    assert climate_options[CONF_SET_TEMP_DIVIDED] is False
    assert climate_options[CONF_TEMP_STEP_OVERRIDE] == STEP_HALVES
    assert climate_options[CONF_MIN_TEMP] == 12
    assert climate_options[CONF_MAX_TEMP] == 22

    light_options = config_entry.options[LIGHT_ID]
    assert light_options[CONF_SUPPORT_COLOR] is True
    assert light_options[CONF_BRIGHTNESS_RANGE_MODE] == 1
    assert light_options[CONF_MIN_KELVIN] == 4000
    assert light_options[CONF_MAX_KELVIN] == 5000
    assert light_options[CONF_TUYA_MAX_COLTEMP] == 12000

    assert config_entry.options[CONF_DISCOVERY_INTERVAL] == 100
    assert config_entry.options[CONF_QUERY_INTERVAL] == 50
    assert config_entry.options[CONF_QUERY_DEVICE] == LIGHT_ID
