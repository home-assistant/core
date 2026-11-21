"""Test the complete flow using the actual Python library and HTTP parsing."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.config import config_entries as config_entries_api
from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import MOCK_INPUT


async def test_http_timeout_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Recover the same entities after a transport timeout in the real library."""
    endpoint = "http://192.0.2.1:80/monitorjson"
    payload = {"SN": "http-meter", "Data": [230, 2, 460, 100, 10]}
    aioclient_mock.get(endpoint, json=payload)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Meter", unique_id="http-meter", data=MOCK_INPUT
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "http-meter_Power"
    )
    original_entities = set(entity_registry.entities)
    assert hass.states.get(entity_id).state == "460"

    aioclient_mock.clear_requests()
    aioclient_mock.get(endpoint, exc=TimeoutError())
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(endpoint, json={**payload, "Data": [230, 3, 690, 101, 10]})
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == "690"
    assert set(entity_registry.entities) == original_entities
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


async def test_http_setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Identify, register and poll a meter through the real library."""
    aioclient_mock.get(
        "http://192.0.2.1:80/monitorjson",
        json={
            "SN": "http-meter",
            "mac": "00:00:00:00:00:01",
            "Data": [230, 2, 460, 100, 10],
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "http-meter"
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "http-meter_Power"
    )
    assert hass.states.get(entity_id).state == "460"
    assert aioclient_mock.call_count == 2
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://192.0.2.1:80/monitorjson",
        json={
            "SN": "http-meter",
            "mac": "00:00:00:00:00:01",
            "Data": [230, 3, 690, 101, 10],
        },
    )
    freezer.tick(timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == "690"


@pytest.mark.usefixtures("mock_setup_entry", "mock_meter")
async def test_config_form_over_http(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Serialize the actual UI schema and submit an HTTP-prefixed address."""
    await async_setup_component(hass, "http", {})
    config_entries_api.async_setup(hass)
    client = await hass_client()
    response = await client.post(
        "/api/config/config_entries/flow", json={"handler": DOMAIN}
    )
    assert response.status == 200
    form = await response.json()
    assert {field["name"] for field in form["data_schema"]} == {
        "host",
        "port",
        "username",
        "password",
    }
    response = await client.post(
        f"/api/config/config_entries/flow/{form['flow_id']}",
        json={
            "host": "http://192.0.2.1:8080/",
            "port": 80,
        },
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == "create_entry"
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].unique_id == "test-meter"
    assert entries[0].options == {}


async def test_full_https_endpoint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """The real library uses the complete anonymous endpoint during setup."""
    url = "https://meter.example/WEM3080/monitorjson?scenario=solar"
    aioclient_mock.get(
        url,
        json={
            "SN": "https-meter",
            "mac": "00:00:00:00:00:01",
            "Data": [230, 2, 460, 100, 10],
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: url, CONF_PORT: 80}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https-meter"
    assert result["data"] == {CONF_HOST: url, CONF_PORT: 443}
    assert aioclient_mock.call_count == 2
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "https-meter_Power"
    )
    assert hass.states.get(entity_id).state == "460"


async def test_simulator_directory_over_http(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """A directory URL entered in the UI requests monitorjson below that path."""
    aioclient_mock.get(
        "http://meter.example/WEM3050T/monitorjson",
        json={
            "SN": "directory-meter",
            "mac": "00:00:00:00:00:01",
            "Datas": [[230, 2, 460, 100, 10, 50, 0.95]] * 4,  # codespell:ignore datas
        },
    )
    await async_setup_component(hass, "http", {})
    config_entries_api.async_setup(hass)
    client = await hass_client()
    response = await client.post(
        "/api/config/config_entries/flow", json={"handler": DOMAIN}
    )
    form = await response.json()
    response = await client.post(
        f"/api/config/config_entries/flow/{form['flow_id']}",
        json={"host": "http://meter.example/WEM3050T/", "port": 80},
    )
    assert response.status == 200
    result = await response.json()
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "directory-meter"
    assert entry.data[CONF_HOST] == "http://meter.example/WEM3050T/monitorjson"
    assert aioclient_mock.call_count == 2
