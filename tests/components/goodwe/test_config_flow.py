"""Test the Goodwe config flow."""
from unittest.mock import AsyncMock, patch

from goodwe import InverterError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.goodwe.const import (
    CONF_MODEL_FAMILY,
    CONF_NETWORK_RETRIES,
    CONF_NETWORK_TIMEOUT,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_SERIAL = "123456789"


def mock_inverter():
    """Get a mock object of the inverter."""
    goodwe_inverter = AsyncMock()
    goodwe_inverter.serial_number = TEST_SERIAL
    return goodwe_inverter


@pytest.fixture(name="goodwe_connect", autouse=True)
def goodwe_connect_fixture():
    """Mock motion blinds connection and entry setup."""
    with patch(
        "homeassistant.components.goodwe.config_flow.connect",
        return_value=mock_inverter(),
    ), patch("homeassistant.components.goodwe.async_setup_entry", return_value=True):
        yield


async def test_config_flow_manual_host_success(hass):
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == data_entry_flow.STEP_ID_USER
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.goodwe.config_flow.connect",
        side_effect=InverterError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == data_entry_flow.STEP_ID_USER
    assert result["errors"] == {"base": "connection_error"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_MODEL_FAMILY: "AsyncMock",
    }


async def test_options_flow(hass):
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_MODEL_FAMILY: "DT"},
        unique_id=TEST_SERIAL,
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == data_entry_flow.STEP_ID_INIT

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 15,
            CONF_NETWORK_RETRIES: 1,
            CONF_NETWORK_TIMEOUT: 3,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        CONF_SCAN_INTERVAL: 15,
        CONF_NETWORK_RETRIES: 1,
        CONF_NETWORK_TIMEOUT: 3,
    }
