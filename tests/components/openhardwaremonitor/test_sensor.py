"""The tests for the Open Hardware Monitor platform."""

import requests_mock

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.components.openhardwaremonitor.const import DOMAIN

from tests.common import load_fixture, MockConfigEntry

from .const import HOST, PORT


async def test_setup_via_yaml(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test for successfully setting up the platform."""
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

    await assert_fixture(hass)


async def test_async_setup_entry(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test async_setup_entry."""
    assert hass.state is CoreState.running

    requests_mock.get(
        f"http://{HOST}:{PORT}/data.json",
        text=load_fixture("openhardwaremonitor.json", "openhardwaremonitor"),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await assert_fixture(hass)


async def assert_fixture(hass: HomeAssistant):
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 38

    state = hass.states.get("sensor.test_pc_intel_core_i7_7700_temperatures_cpu_core_1")

    assert state is not None
    assert state.state == "31.0"

    state = hass.states.get("sensor.test_pc_intel_core_i7_7700_temperatures_cpu_core_2")

    assert state is not None
    assert state.state == "30.0"
