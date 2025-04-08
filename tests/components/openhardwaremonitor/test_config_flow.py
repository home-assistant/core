"""The tests for the Open Hardware Monitor platform."""

import requests_mock
from unittest.moock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from homeassistant.components.openhardwaremonitor.const import DOMAIN

from tests.common import MockConfigEntry, load_fixture

HOST = "localhost"
PORT = 8011

async def test_user(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{HOST:PORT}"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST:PORT}"

async def test_import(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test user config."""
    config = {
        "sensor": {
            "platform": "openhardwaremonitor",
            "host": HOST,
            "port": PORT,
        }
    }

    requests_mock.get(
        f"http://{HOST}:{PORT}/data.json",
        text=load_fixture("openhardwaremonitor.json", "openhardwaremonitor"),
    )

    await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 38

    state = hass.states.get("sensor.test_pc_intel_core_i7_7700_temperatures_cpu_core_1")

    assert state is not None
    assert state.state == "31.0"

    state = hass.states.get("sensor.test_pc_intel_core_i7_7700_temperatures_cpu_core_2")

    assert state is not None
    assert state.state == "30.0"
