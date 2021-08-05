"""Tests for SpeedTest config flow."""
from datetime import timedelta
from unittest.mock import MagicMock

from speedtest import NoMatchedServers

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import speedtestdotnet
from homeassistant.components.speedtestdotnet.const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DOMAIN,
    SENSOR_TYPES,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_flow_works(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        speedtestdotnet.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_import_fails(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test import step fails if server_id is not valid."""

    mock_api.return_value.get_servers.side_effect = NoMatchedServers
    result = await hass.config_entries.flow.async_init(
        speedtestdotnet.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_SERVER_ID: "223",
            CONF_MANUAL: True,
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_MONITORED_CONDITIONS: list(SENSOR_TYPES),
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "wrong_server_id"


async def test_import_success(hass):
    """Test import step is successful if server_id is valid."""

    result = await hass.config_entries.flow.async_init(
        speedtestdotnet.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_SERVER_ID: "1",
            CONF_MANUAL: True,
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_MONITORED_CONDITIONS: list(SENSOR_TYPES),
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "SpeedTest"
    assert result["data"][CONF_SERVER_ID] == "1"
    assert result["data"][CONF_MANUAL] is True
    assert result["data"][CONF_SCAN_INTERVAL] == 1


async def test_options(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SpeedTest",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SERVER_NAME: "Country1 - Sponsor1 - Server1",
            CONF_SCAN_INTERVAL: 30,
            CONF_MANUAL: True,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_SERVER_NAME: "Country1 - Sponsor1 - Server1",
        CONF_SERVER_ID: "1",
        CONF_SCAN_INTERVAL: 30,
        CONF_MANUAL: True,
    }
    await hass.async_block_till_done()

    assert hass.data[DOMAIN].update_interval is None

    # test setting the option to update periodically
    result2 = await hass.config_entries.options.async_init(entry.entry_id)
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            CONF_SERVER_NAME: "Country1 - Sponsor1 - Server1",
            CONF_SCAN_INTERVAL: 30,
            CONF_MANUAL: False,
        },
    )
    await hass.async_block_till_done()

    assert hass.data[DOMAIN].update_interval == timedelta(minutes=30)


async def test_integration_already_configured(hass: HomeAssistant) -> None:
    """Test integration is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        speedtestdotnet.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"
