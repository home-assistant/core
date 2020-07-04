"""Tests for the Tuya config flow."""
import pytest
from tuyaha.tuyaapi import TuyaAPIException, TuyaNetException

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.tuya.const import CONF_COUNTRYCODE, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME

from tests.async_mock import Mock, patch
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


async def test_user(hass, tuya):
    """Test user config."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.tuya.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.tuya.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TUYA_USER_DATA
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_COUNTRYCODE] == COUNTRY_CODE
    assert result["data"][CONF_PLATFORM] == TUYA_PLATFORM
    assert not result["result"].unique_id

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass, tuya):
    """Test import step."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.tuya.async_setup", return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.tuya.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TUYA_USER_DATA,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_COUNTRYCODE] == COUNTRY_CODE
    assert result["data"][CONF_PLATFORM] == TUYA_PLATFORM
    assert not result["result"].unique_id

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_setup(hass, tuya):
    """Test we abort if Tuya is already setup."""
    MockConfigEntry(domain=DOMAIN, data=TUYA_USER_DATA).add_to_hass(hass)

    # Should fail, config exist (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"

    # Should fail, config exist (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_abort_on_invalid_credentials(hass, tuya):
    """Test when we have invalid credentials."""
    tuya().init.side_effect = TuyaAPIException("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "auth_failed"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "auth_failed"


async def test_abort_on_connection_error(hass, tuya):
    """Test when we have a network error."""
    tuya().init.side_effect = TuyaNetException("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "conn_error"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TUYA_USER_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "conn_error"
