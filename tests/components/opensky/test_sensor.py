"""OpenSky sensor tests."""
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.opensky.const import (
    EVENT_OPENSKY_ENTRY,
    EVENT_OPENSKY_EXIT,
)
from homeassistant.core import Event, HomeAssistant

from . import get_states_response_fixture
from .conftest import ComponentSetup

from tests.common import MockConfigEntry, async_fire_time_changed


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
