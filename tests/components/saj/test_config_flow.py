"""Tests for SAJ config flow."""
from unittest.mock import Mock, patch

import pysaj
import pytest

from homeassistant.components.saj.const import DOMAIN
from homeassistant.components.saj.coordinator import CannotConnect
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_CREATE_ENTRY

MOCK_USER_DATA = {
    CONF_HOST: "localhost",
    CONF_TYPE: "wifi",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "foobar",
}
MOCK_IMPORT_DATA = {
    CONF_HOST: "localhost",
    CONF_NAME: "Inverter",
    CONF_TYPE: "wifi",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "foobar",
}


@pytest.fixture(name="inverter", scope="module")
def remote_fixture():
    """Patch the SAJDataUpdateCoordinator."""

    with patch(
        "homeassistant.components.saj.coordinator.SAJDataUpdateCoordinator"
    ) as inverter_class:
        inverter = Mock()

        async def mock_connect():
            if inverter.error:
                err = inverter.error
                inverter.error = None
                raise err

        inverter.connect = mock_connect
        inverter.get_enabled_sensors = lambda: ["a", "b"]
        inverter.name = "mock inverter name"
        inverter.serialnumber = "mock_serial_123"
        inverter_class.return_value = inverter
        yield inverter


async def test_unknown_error(hass, inverter):
    """Test unknown error."""
    inverter.error = Exception("mock error")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["errors"]["base"] == "unknown"


async def test_cannot_connect(hass, inverter):
    """Test connection error."""
    inverter.error = CannotConnect()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"

    default_values = result["data_schema"]({})
    assert default_values[CONF_TYPE] == "wifi"
    assert default_values[CONF_HOST] == "localhost"


async def test_invalid_auth(hass, inverter):
    """Test invalid auth."""
    inverter.error = pysaj.UnauthorizedException("mock error")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"

    default_values = result["data_schema"]({})
    assert default_values[CONF_USERNAME] == "admin"
    assert default_values[CONF_PASSWORD] == "foobar"


async def test_success(hass, inverter):
    """Test starting a flow by user."""
    # show form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "mock inverter name"
    assert result["data"][CONF_HOST] == "localhost"
    assert result["data"][CONF_TYPE] == "wifi"


async def test_already_configured(hass, inverter):
    """Test starting a flow by user when already configured."""

    # entry was added
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"

    # failed as already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import(hass, inverter):
    """Test import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_IMPORT_DATA
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY


async def test_already_imported(hass, inverter):
    """Test import flow when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_IMPORT_DATA
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_IMPORT_DATA
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
