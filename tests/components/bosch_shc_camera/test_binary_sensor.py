"""Test the Bosch Smart Home Camera binary sensor platform."""

from datetime import timedelta
import time
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_shc_camera.const import CLOUD_API
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

CAM_ID = "aabbccdd-1122-3344-5566-778899001122"
MOTION_ENTITY_ID = "binary_sensor.bosch_terrasse_motion"
PERSON_ENTITY_ID = "binary_sensor.bosch_terrasse_person_detected"
AUDIO_ENTITY_ID = "binary_sensor.bosch_terrasse_audio_alarm"
LAN_ENTITY_ID = "binary_sensor.bosch_terrasse_lan_reachable"


def _mock_video_inputs(
    aioclient_mock: AiohttpClientMocker, *, has_sound: bool = False
) -> None:
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs",
        json=[
            {
                "id": CAM_ID,
                "title": "Terrasse",
                "hardwareVersion": "HOME_Eyes_Outdoor",
                "firmwareVersion": "9.40.104",
                "privacyMode": "OFF",
                "featureSupport": {"sound": has_sound},
            }
        ],
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})


def _mock_events(aioclient_mock: AiohttpClientMocker, events: list[dict]) -> None:
    """Register the polled-events endpoints a non-first coordinator tick needs.

    `last_event` returning a 404 forces the coordinator down the full-fetch
    path (`event_polling.py::_fetch_one_camera_events`) instead of the
    unchanged-id skip shortcut, so the mocked `events` list is always used.
    """
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/last_event", status=404)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/events?videoInputId={CAM_ID}&limit=20", json=events
    )


def _event(event_type: str, *, age: timedelta, tags: list[str] | None = None) -> dict:
    ts = dt_util.utcnow() - age
    event: dict = {
        "id": f"evt-{event_type.lower()}",
        "eventType": event_type,
        "timestamp": ts.isoformat(),
    }
    if tags is not None:
        event["eventTags"] = tags
    return event


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A camera with sound support creates all 4 binary sensors, snapshotted."""
    _mock_video_inputs(aioclient_mock, has_sound=True)
    _mock_events(aioclient_mock, [])

    with patch(
        "homeassistant.components.bosch_shc_camera.ALL_PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, config_entry)
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_no_sound_support_skips_audio_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A camera without `featureSupport.sound` gets no Audio Alarm sensor."""
    _mock_video_inputs(aioclient_mock, has_sound=False)
    _mock_events(aioclient_mock, [])

    await setup_integration(hass, config_entry)

    assert entity_registry.async_get(AUDIO_ENTITY_ID) is None
    assert entity_registry.async_get(MOTION_ENTITY_ID) is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_sensor_recent_event_is_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A MOVEMENT event within the active window turns the motion sensor on."""
    _mock_video_inputs(aioclient_mock)
    _mock_events(aioclient_mock, [_event("MOVEMENT", age=timedelta(seconds=5))])

    await setup_integration(hass, config_entry)
    await config_entry.runtime_data.async_refresh()

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes["event_id"] == "evt-movement"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_sensor_stale_event_is_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A MOVEMENT event outside the default 90 s active window is off."""
    _mock_video_inputs(aioclient_mock)
    _mock_events(aioclient_mock, [_event("MOVEMENT", age=timedelta(seconds=200))])

    await setup_integration(hass, config_entry)
    await config_entry.runtime_data.async_refresh()

    assert hass.states.get(MOTION_ENTITY_ID).state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_sensor_no_event_is_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """No events at all leaves the motion sensor off with empty attributes."""
    _mock_video_inputs(aioclient_mock)
    _mock_events(aioclient_mock, [])

    await setup_integration(hass, config_entry)
    await config_entry.runtime_data.async_refresh()

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state.state == STATE_OFF
    assert "event_id" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_person_sensor_matches_explicit_person_type(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A bare eventType=PERSON (Gen1 style) turns the person sensor on."""
    _mock_video_inputs(aioclient_mock)
    _mock_events(aioclient_mock, [_event("PERSON", age=timedelta(seconds=5))])

    await setup_integration(hass, config_entry)
    await config_entry.runtime_data.async_refresh()

    assert hass.states.get(PERSON_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_person_sensor_matches_movement_tagged_person(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Gen2 cameras report a person as MOVEMENT + eventTags=[PERSON] (issue #36)."""
    _mock_video_inputs(aioclient_mock)
    _mock_events(
        aioclient_mock,
        [_event("MOVEMENT", age=timedelta(seconds=5), tags=["PERSON"])],
    )

    await setup_integration(hass, config_entry)
    await config_entry.runtime_data.async_refresh()

    assert hass.states.get(PERSON_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_person_sensor_ignores_untagged_movement(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A plain MOVEMENT event with no PERSON tag does not trigger the person sensor."""
    _mock_video_inputs(aioclient_mock)
    _mock_events(aioclient_mock, [_event("MOVEMENT", age=timedelta(seconds=5))])

    await setup_integration(hass, config_entry)
    await config_entry.runtime_data.async_refresh()

    assert hass.states.get(PERSON_ENTITY_ID).state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_audio_alarm_sensor_on_within_window(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A camera with sound support and a recent AUDIO_ALARM event is on."""
    _mock_video_inputs(aioclient_mock, has_sound=True)
    _mock_events(aioclient_mock, [_event("AUDIO_ALARM", age=timedelta(seconds=5))])

    await setup_integration(hass, config_entry)
    await config_entry.runtime_data.async_refresh()

    assert hass.states.get(AUDIO_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_active_window_option_respected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A shortened `motion_active_window` option turns an older event off sooner."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={**config_entry.options, "motion_active_window": 10},
    )
    _mock_video_inputs(aioclient_mock)
    _mock_events(aioclient_mock, [_event("MOVEMENT", age=timedelta(seconds=30))])

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await config_entry.runtime_data.async_refresh()

    assert hass.states.get(MOTION_ENTITY_ID).state == STATE_OFF


async def test_lan_reachable_unknown_before_any_probe(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Before any TCP probe has run, LAN reachability is unknown (enabled by default)."""
    _mock_video_inputs(aioclient_mock)
    _mock_events(aioclient_mock, [])

    await setup_integration(hass, config_entry)

    assert hass.states.get(LAN_ENTITY_ID).state == STATE_UNKNOWN


async def test_lan_reachable_reflects_tcp_probe_result(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The LAN-reachable sensor reflects `coordinator.lan_tcp_reachable`.

    `async_local_tcp_ping` is a raw `asyncio.open_connection` probe, not a
    Bosch cloud call — there is no aioclient_mock endpoint to drive it
    through. `lan_tcp_reachable` is the coordinator's own public result
    cache that this entity is documented to read directly (see
    `binary_sensor.py::BoschLanReachableBinarySensor.is_on`); mutating it
    and calling the coordinator's public `async_update_listeners()` (the
    same call `CoordinatorEntity` uses internally to push a fresh state)
    reproduces a real probe's effect without reaching into any private
    entity internals.
    """
    _mock_video_inputs(aioclient_mock)
    _mock_events(aioclient_mock, [])

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    coordinator.lan_tcp_reachable[CAM_ID] = (True, time.monotonic())
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(LAN_ENTITY_ID).state == STATE_ON

    coordinator.lan_tcp_reachable[CAM_ID] = (False, time.monotonic())
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(LAN_ENTITY_ID).state == STATE_OFF
