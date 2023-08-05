"""OpenSky sensor tests."""
from datetime import timedelta
from unittest.mock import patch

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
from homeassistant.util import dt as dt_util

from . import MockOpenSky
from .conftest import ComponentSetup

from tests.common import MockConfigEntry, async_fire_time_changed

LEGACY_CONFIG = {Platform.SENSOR: [{CONF_PLATFORM: DOMAIN, CONF_RADIUS: 10.0}]}


async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test migration from yaml to config flow."""
    with patch(
        "homeassistant.components.opensky.OpenSky",
        return_value=MockOpenSky(),
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
    await setup_integration(config_entry, MockOpenSky())

    state = hass.states.get("sensor.opensky")
    assert state == snapshot


async def test_sensor_altitude(
    hass: HomeAssistant,
    config_entry_altitude: MockConfigEntry,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
):
    """Test setup sensor with a set altitude."""
    await setup_integration(config_entry_altitude, MockOpenSky())

    state = hass.states.get("sensor.opensky")
    assert state == snapshot


async def test_sensor_updating(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
):
    """Test updating sensor."""
    await setup_integration(
        config_entry,
        MockOpenSky(
            states_fixture_cycle=[
                "opensky/states.json",
                "opensky/states_1.json",
                "opensky/states.json",
            ]
        ),
    )
    events = []

    async def event_listener(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_OPENSKY_ENTRY, event_listener)
    hass.bus.async_listen(EVENT_OPENSKY_EXIT, event_listener)

    async def skip_time_and_check_events() -> None:
        future = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert events == snapshot

    await skip_time_and_check_events()
    await skip_time_and_check_events()
