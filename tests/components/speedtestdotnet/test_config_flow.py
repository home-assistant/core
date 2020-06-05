"""Tests for SpeedTest config flow."""
import pytest

from homeassistant import data_entry_flow
from homeassistant.components import speedtestdotnet
from homeassistant.components.speedtestdotnet.const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_SCAN_INTERVAL

from . import MOCK_SERVERS

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.fixture(name="mock_setup", autouse=True)
def mock_setup():
    """Mock entry setup."""
    with patch(
        "homeassistant.components.speedtestdotnet.async_setup_entry", return_value=True,
    ):
        yield


async def test_flow_works(hass):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        speedtestdotnet.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "SpeedTest"


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(domain=DOMAIN, title="SpeedTest", data={}, options={},)
    entry.add_to_hass(hass)

    hass.data[DOMAIN] = speedtestdotnet.SpeedTestDataCoordinator(hass, entry)
    hass.data[DOMAIN].servers = MOCK_SERVERS

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SERVER_NAME: "Server1",
            CONF_SCAN_INTERVAL: 30,
            CONF_MANUAL: False,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_SERVER_NAME: "Server1",
        CONF_SERVER_ID: "1",
        CONF_SCAN_INTERVAL: 30,
        CONF_MANUAL: False,
    }


async def test_integration_already_configured(hass):
    """Test integration is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={},)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        speedtestdotnet.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "one_instance_allowed"
