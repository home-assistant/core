"""Test sensor of Airly integration."""

from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from airly.exceptions import AirlyError
from syrupy import SnapshotAssertion

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import API_POINT_URL, init_integration

from tests.common import async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensor(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.airly.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass, aioclient_mock)

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_availability(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.35"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        API_POINT_URL, exc=AirlyError(HTTPStatus.NOT_FOUND, {"message": "Not found"})
    )
    future = utcnow() + timedelta(minutes=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_POINT_URL, text=load_fixture("valid_station.json", "airly"))
    future = utcnow() + timedelta(minutes=120)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.35"


async def test_manual_update_entity(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass, aioclient_mock)

    call_count = aioclient_mock.call_count
    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.home_humidity"]},
        blocking=True,
    )

    assert aioclient_mock.call_count == call_count + 1
