"""OpenSky sensor tests."""
from datetime import timedelta
import json
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from python_opensky import StatesResponse
from syrupy import SnapshotAssertion

from homeassistant.components.opensky.const import (
    DOMAIN,
    EVENT_OPENSKY_ENTRY,
    EVENT_OPENSKY_EXIT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PLATFORM, CONF_RADIUS, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture

LEGACY_CONFIG = {Platform.SENSOR: [{CONF_PLATFORM: DOMAIN, CONF_RADIUS: 10.0}]}


async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test migration from yaml to config flow."""
    json_fixture = load_fixture("opensky/states.json")
    with patch(
        "python_opensky.OpenSky.get_states",
        return_value=StatesResponse.parse_obj(json.loads(json_fixture)),
    ):
        assert await async_setup_component(hass, Platform.SENSOR, LEGACY_CONFIG)
        await hass.async_block_till_done()
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].state is ConfigEntryState.LOADED
        issue_registry = ir.async_get(hass)
        assert len(issue_registry.issues) == 1


async def test_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
):
    """Test setup sensor."""
    await setup_integration(config_entry)

    state = hass.states.get("sensor.opensky")
    assert state == snapshot
    events = []

    async def event_listener(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_OPENSKY_ENTRY, event_listener)
    hass.bus.async_listen(EVENT_OPENSKY_EXIT, event_listener)
    assert events == []


async def test_sensor_altitude(
    hass: HomeAssistant,
    config_entry_altitude: MockConfigEntry,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
):
    """Test setup sensor with a set altitude."""
    await setup_integration(config_entry_altitude)

    state = hass.states.get("sensor.opensky")
    assert state == snapshot


async def test_sensor_updating(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
):
    """Test updating sensor."""
    await setup_integration(config_entry)

    def get_states_response_fixture(fixture: str) -> StatesResponse:
        json_fixture = load_fixture(fixture)
        return StatesResponse.parse_obj(json.loads(json_fixture))

    events = []

    async def event_listener(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_OPENSKY_ENTRY, event_listener)
    hass.bus.async_listen(EVENT_OPENSKY_EXIT, event_listener)

    async def skip_time_and_check_events() -> None:
        freezer.tick(timedelta(minutes=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert events == snapshot

    with patch(
        "python_opensky.OpenSky.get_states",
        return_value=get_states_response_fixture("opensky/states_1.json"),
    ):
        await skip_time_and_check_events()
    with patch(
        "python_opensky.OpenSky.get_states",
        return_value=get_states_response_fixture("opensky/states.json"),
    ):
        await skip_time_and_check_events()
