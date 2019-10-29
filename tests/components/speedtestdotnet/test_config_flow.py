"""Tests for SpeedTest config flow."""
from datetime import timedelta

from homeassistant.components.speedtestdotnet import config_flow

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.components.speedtestdotnet.const import (
    DOMAIN,
    CONF_SERVER_ID,
    CONF_MANUAL,
)
from tests.common import MockConfigEntry


async def test_flow_works(hass):
    """Test user config."""
    flow = config_flow.SpeedTestFlowHandler()
    flow.hass = hass

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form", result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    assert result["title"] == "SpeedTest"


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SpeedTest",
        data={},
        options={CONF_SCAN_INTERVAL: 60, CONF_SERVER_ID: 2229, CONF_MANUAL: False},
    )
    flow = config_flow.SpeedTestFlowHandler()
    flow.hass = hass
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await options_flow.async_step_init(
        {CONF_SCAN_INTERVAL: 10, CONF_MANUAL: True, CONF_SERVER_ID: 2231}
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_SCAN_INTERVAL] == 10
    assert result["data"][CONF_SERVER_ID] == 2231
    assert result["data"][CONF_MANUAL] is True

    # Test server_id doesn't exist

    result = await options_flow.async_step_init(
        {CONF_SCAN_INTERVAL: 10, CONF_MANUAL: True, CONF_SERVER_ID: 0}
    )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_SERVER_ID: "wrong_serverid"}


async def test_import(hass):
    """Test import step."""
    flow = config_flow.SpeedTestFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(
        {
            CONF_SERVER_ID: 2231,
            CONF_MANUAL: True,
            CONF_SCAN_INTERVAL: timedelta(minutes=30),
        }
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "SpeedTest"
    assert result["data"][CONF_MANUAL] is True
    assert result["data"][CONF_SERVER_ID] == 2231
    assert result["data"][CONF_SCAN_INTERVAL] == 30


async def test_integration_already_configured(hass):
    """Test integration is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={},)
    entry.add_to_hass(hass)
    flow = config_flow.SpeedTestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "one_instance_allowed"
