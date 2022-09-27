"""Tests for SpeedTest config flow."""
from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import speedtestdotnet
from homeassistant.components.speedtestdotnet.const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_flow_works(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        speedtestdotnet.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


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
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SERVER_NAME: "Country1 - Sponsor1 - Server1",
            CONF_SCAN_INTERVAL: 30,
            CONF_MANUAL: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SERVER_NAME: "Country1 - Sponsor1 - Server1",
        CONF_SERVER_ID: "1",
        CONF_SCAN_INTERVAL: 30,
        CONF_MANUAL: True,
    }
    await hass.async_block_till_done()

    assert hass.data[DOMAIN].update_interval is None

    # test setting server name to "*Auto Detect"
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SERVER_NAME: "*Auto Detect",
            CONF_SCAN_INTERVAL: 30,
            CONF_MANUAL: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SERVER_NAME: "*Auto Detect",
        CONF_SERVER_ID: None,
        CONF_SCAN_INTERVAL: 30,
        CONF_MANUAL: True,
    }

    # test setting the option to update periodically
    result2 = await hass.config_entries.options.async_init(entry.entry_id)
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
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
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
