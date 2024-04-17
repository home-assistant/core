"""OpenSky sensor tests."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from python_opensky import StatesResponse
from syrupy import SnapshotAssertion

from homeassistant.components.opensky.const import (
    DOMAIN,
    EVENT_OPENSKY_ENTRY,
    EVENT_OPENSKY_EXIT,
)
from homeassistant.core import Event, HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)
from tests.components.opensky import setup_integration


async def test_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    opensky_client: AsyncMock,
):
    """Test setup sensor."""
    await setup_integration(hass, config_entry)

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
    opensky_client: AsyncMock,
    snapshot: SnapshotAssertion,
):
    """Test setup sensor with a set altitude."""
    await setup_integration(hass, config_entry_altitude)

    state = hass.states.get("sensor.opensky")
    assert state == snapshot


async def test_sensor_updating(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    opensky_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
):
    """Test updating sensor."""
    await setup_integration(hass, config_entry)

    events = []

    async def event_listener(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_OPENSKY_ENTRY, event_listener)
    hass.bus.async_listen(EVENT_OPENSKY_EXIT, event_listener)

    async def skip_time_and_check_events() -> None:
        freezer.tick(timedelta(minutes=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert events == snapshot

    opensky_client.get_states.return_value = StatesResponse.from_api(
        load_json_object_fixture("states_1.json", DOMAIN)
    )
    await skip_time_and_check_events()
    opensky_client.get_states.return_value = StatesResponse.from_api(
        load_json_object_fixture("states.json", DOMAIN)
    )
    await skip_time_and_check_events()
