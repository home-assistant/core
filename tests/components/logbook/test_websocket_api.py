"""The tests for the logbook component."""
import asyncio
from collections.abc import Callable
from datetime import timedelta
from unittest.mock import ANY, patch

from freezegun import freeze_time
import pytest

from homeassistant import core
from homeassistant.components import logbook, recorder
from homeassistant.components.automation import ATTR_SOURCE, EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.logbook import websocket_api
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.util import get_instance
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entityfilter import CONF_ENTITY_GLOBS
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import (
    async_block_recorder,
    async_recorder_block_till_done,
    async_wait_recording_done,
)
from tests.typing import RecorderInstanceGenerator, WebSocketGenerator


@pytest.fixture
def set_utc(hass):
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


def listeners_without_writes(listeners: dict[str, int]) -> dict[str, int]:
    """Return listeners without final write listeners since we are not testing for these."""
    return {
        key: value
        for key, value in listeners.items()
        if key != EVENT_HOMEASSISTANT_FINAL_WRITE
    }


async def _async_mock_logbook_platform_with_broken_describe(
    hass: HomeAssistant,
) -> None:
    class MockLogbookPlatform:
        """Mock a logbook platform with broken describe."""

        @core.callback
        def async_describe_events(
            hass: HomeAssistant,  # noqa: N805
            async_describe_event: Callable[
                [str, str, Callable[[Event], dict[str, str]]], None
            ],
        ) -> None:
            """Describe logbook events."""

            @core.callback
            def async_describe_test_event(event: Event) -> dict[str, str]:
                """Describe mock logbook event."""
                raise ValueError("Broken")

            async_describe_event("test", "mock_event", async_describe_test_event)

    await logbook._process_logbook_platform(hass, "test", MockLogbookPlatform)


async def _async_mock_logbook_platform(hass: HomeAssistant) -> None:
    class MockLogbookPlatform:
        """Mock a logbook platform."""

        @core.callback
        def async_describe_events(
            hass: HomeAssistant,  # noqa: N805
            async_describe_event: Callable[
                [str, str, Callable[[Event], dict[str, str]]], None
            ],
        ) -> None:
            """Describe logbook events."""

            @core.callback
            def async_describe_test_event(event: Event) -> dict[str, str]:
                """Describe mock logbook event."""
                return {
                    "name": "device name",
                    "message": event.data.get("message", "is on fire"),
                }

            async_describe_event("test", "mock_event", async_describe_test_event)

    await logbook._process_logbook_platform(hass, "test", MockLogbookPlatform)


async def _async_mock_entity_with_broken_logbook_platform(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> er.RegistryEntry:
    """Mock an integration that provides an entity that are described by the logbook that raises."""
    entry = MockConfigEntry(domain="test", data={"first": True}, options=None)
    entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        platform="test",
        domain="sensor",
        config_entry=entry,
        unique_id="1234",
        suggested_object_id="test",
    )
    await _async_mock_logbook_platform_with_broken_describe(hass)
    return entry


async def _async_mock_entity_with_logbook_platform(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> er.RegistryEntry:
    """Mock an integration that provides an entity that are described by the logbook."""
    entry = MockConfigEntry(domain="test", data={"first": True}, options=None)
    entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        platform="test",
        domain="sensor",
        config_entry=entry,
        unique_id="1234",
        suggested_object_id="test",
    )
    await _async_mock_logbook_platform(hass)
    return entry


async def _async_mock_devices_with_logbook_platform(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> list[dr.DeviceEntry]:
    """Mock an integration that provides a device that are described by the logbook."""
    entry = MockConfigEntry(domain="test", data={"first": True}, options=None)
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="device name",
        manufacturer="manufacturer",
        model="model",
        suggested_area="Game Room",
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:CC")},
        identifiers={("bridgeid", "4567")},
        sw_version="sw-version",
        name="device name",
        manufacturer="manufacturer",
        model="model",
        suggested_area="Living Room",
    )
    await _async_mock_logbook_platform(hass)
    return [device, device2]


async def test_get_events(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test logbook get_events."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set("light.kitchen", STATE_OFF)
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 200})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 300})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 400})
    await hass.async_block_till_done()
    context = core.Context(
        id="01GTDGKBCH00GW0X276W5TEDDD",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )

    hass.states.async_set("light.kitchen", STATE_OFF, context=context)
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "entity_ids": ["light.kitchen"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    await client.send_json(
        {
            "id": 2,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2
    assert response["result"] == []

    await client.send_json(
        {
            "id": 3,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "entity_ids": ["light.kitchen"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 3

    results = response["result"]
    assert results[0]["entity_id"] == "light.kitchen"
    assert results[0]["state"] == "on"
    assert results[1]["entity_id"] == "light.kitchen"
    assert results[1]["state"] == "off"

    await client.send_json(
        {
            "id": 4,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 4

    results = response["result"]
    assert len(results) == 3
    assert results[0]["message"] == "started"
    assert results[1]["entity_id"] == "light.kitchen"
    assert results[1]["state"] == "on"
    assert isinstance(results[1]["when"], float)
    assert results[2]["entity_id"] == "light.kitchen"
    assert results[2]["state"] == "off"
    assert isinstance(results[2]["when"], float)

    await client.send_json(
        {
            "id": 5,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "context_id": "01GTDGKBCH00GW0X276W5TEDDD",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 5

    results = response["result"]
    assert len(results) == 1
    assert results[0]["entity_id"] == "light.kitchen"
    assert results[0]["state"] == "off"
    assert isinstance(results[0]["when"], float)


async def test_get_events_entities_filtered_away(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test logbook get_events all entities filtered away."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set("light.kitchen", STATE_ON)
    await hass.async_block_till_done()
    hass.states.async_set(
        "light.filtered", STATE_ON, {"brightness": 100, ATTR_UNIT_OF_MEASUREMENT: "any"}
    )
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_OFF, {"brightness": 200})
    await hass.async_block_till_done()
    hass.states.async_set(
        "light.filtered",
        STATE_OFF,
        {"brightness": 300, ATTR_UNIT_OF_MEASUREMENT: "any"},
    )

    await async_wait_recording_done(hass)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "entity_ids": ["light.kitchen"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1

    results = response["result"]
    assert results[0]["entity_id"] == "light.kitchen"
    assert results[0]["state"] == "off"

    await client.send_json(
        {
            "id": 2,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "entity_ids": ["light.filtered"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2

    results = response["result"]
    assert len(results) == 0


async def test_get_events_future_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_events with a future start time."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)
    future = dt_util.utcnow() + timedelta(hours=10)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": future.isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1

    results = response["result"]
    assert isinstance(results, list)
    assert len(results) == 0


async def test_get_events_bad_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_events bad start time."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": "cats",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_start_time"


async def test_get_events_bad_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_events bad end time."""
    now = dt_util.utcnow()
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "end_time": "dogs",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"


async def test_get_events_invalid_filters(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_events invalid filters."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "entity_ids": [],
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
    await client.send_json(
        {
            "id": 2,
            "type": "logbook/get_events",
            "device_ids": [],
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_get_events_with_device_ids(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test logbook get_events for device ids."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )

    devices = await _async_mock_devices_with_logbook_platform(hass, device_registry)
    device = devices[0]
    device2 = devices[1]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire("mock_event", {"device_id": device.id})
    hass.bus.async_fire("mock_event", {"device_id": device2.id})

    hass.states.async_set("light.kitchen", STATE_OFF)
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 200})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 300})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 400})
    await hass.async_block_till_done()
    context = core.Context(
        id="01GTDGKBCH00GW0X276W5TEDDD",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )

    hass.states.async_set("light.kitchen", STATE_OFF, context=context)
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "device_ids": [device.id, device2.id],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1

    results = response["result"]
    assert len(results) == 2
    assert results[0]["name"] == "device name"
    assert results[0]["message"] == "is on fire"
    assert isinstance(results[0]["when"], float)
    assert results[1]["name"] == "device name"
    assert results[1]["message"] == "is on fire"
    assert isinstance(results[1]["when"], float)

    await client.send_json(
        {
            "id": 2,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "entity_ids": ["light.kitchen"],
            "device_ids": [device.id],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2

    results = response["result"]
    assert results[0]["domain"] == "test"
    assert results[0]["message"] == "is on fire"
    assert results[0]["name"] == "device name"
    assert results[1]["entity_id"] == "light.kitchen"
    assert results[1]["state"] == "on"
    assert results[2]["entity_id"] == "light.kitchen"
    assert results[2]["state"] == "off"

    await client.send_json(
        {
            "id": 3,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 3

    results = response["result"]
    assert len(results) == 5
    assert results[0]["message"] == "started"
    assert results[1]["name"] == "device name"
    assert results[1]["message"] == "is on fire"
    assert isinstance(results[1]["when"], float)
    assert results[2]["name"] == "device name"
    assert results[2]["message"] == "is on fire"
    assert isinstance(results[2]["when"], float)
    assert results[3]["entity_id"] == "light.kitchen"
    assert results[3]["state"] == "on"
    assert isinstance(results[3]["when"], float)
    assert results[4]["entity_id"] == "light.kitchen"
    assert results[4]["state"] == "off"
    assert isinstance(results[4]["when"], float)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream_excluded_entities(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream with excluded entities."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "automation", "script")
        ]
    )
    await async_setup_component(
        hass,
        logbook.DOMAIN,
        {
            logbook.DOMAIN: {
                CONF_EXCLUDE: {
                    CONF_ENTITIES: ["light.exc"],
                    CONF_DOMAINS: ["switch"],
                    CONF_ENTITY_GLOBS: ["*.excluded"],
                }
            },
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("light.exc", STATE_ON)
    hass.states.async_set("light.exc", STATE_OFF)
    hass.states.async_set("switch.any", STATE_ON)
    hass.states.async_set("switch.any", STATE_OFF)
    hass.states.async_set("cover.excluded", STATE_ON)
    hass.states.async_set("cover.excluded", STATE_OFF)

    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {"id": 7, "type": "logbook/event_stream", "start_time": now.isoformat()}
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]
    assert msg["event"]["start_time"] == now.timestamp()
    assert msg["event"]["end_time"] > msg["event"]["start_time"]
    assert msg["event"]["partial"] is True

    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == []

    hass.states.async_set("light.exc", STATE_ON)
    hass.states.async_set("light.exc", STATE_OFF)
    hass.states.async_set("switch.any", STATE_ON)
    hass.states.async_set("switch.any", STATE_OFF)
    hass.states.async_set("cover.excluded", STATE_ON)
    hass.states.async_set("cover.excluded", STATE_OFF)
    hass.states.async_set("light.alpha", "on")
    hass.states.async_set("light.alpha", "off")
    alpha_off_state: State = hass.states.get("light.alpha")
    hass.states.async_set("light.zulu", "on", {"color": "blue"})
    hass.states.async_set("light.zulu", "off", {"effect": "help"})
    zulu_off_state: State = hass.states.get("light.zulu")
    hass.states.async_set(
        "light.zulu", "on", {"effect": "help", "color": ["blue", "green"]}
    )
    zulu_on_state: State = hass.states.get("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_remove("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_set("light.zulu", "on", {"effect": "help", "color": "blue"})
    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == [
        {
            "entity_id": "light.alpha",
            "state": "off",
            "when": alpha_off_state.last_updated.timestamp(),
        },
        {
            "entity_id": "light.zulu",
            "state": "off",
            "when": zulu_off_state.last_updated.timestamp(),
        },
        {
            "entity_id": "light.zulu",
            "state": "on",
            "when": zulu_on_state.last_updated.timestamp(),
        },
    ]

    await async_wait_recording_done(hass)
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: "cover.excluded"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {
            ATTR_NAME: "Mock automation switch matching entity",
            ATTR_ENTITY_ID: "switch.match_domain",
        },
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation switch matching domain", ATTR_DOMAIN: "switch"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation matches nothing"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: "light.keep"},
    )
    hass.states.async_set("cover.excluded", STATE_ON)
    hass.states.async_set("cover.excluded", STATE_OFF)
    await hass.async_block_till_done()
    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": None,
            "message": "triggered",
            "name": "Mock automation matches nothing",
            "source": None,
            "when": ANY,
        },
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": "light.keep",
            "message": "triggered",
            "name": "Mock automation 3",
            "source": None,
            "when": ANY,
        },
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream_included_entities(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream with included entities."""
    test_entities = (
        "light.inc",
        "switch.any",
        "cover.included",
        "cover.not_included",
        "automation.not_included",
        "binary_sensor.is_light",
    )

    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "automation", "script")
        ]
    )
    await async_setup_component(
        hass,
        logbook.DOMAIN,
        {
            logbook.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_ENTITIES: ["light.inc"],
                    CONF_DOMAINS: ["switch"],
                    CONF_ENTITY_GLOBS: ["*.included"],
                }
            },
        },
    )
    await hass.async_block_till_done()

    for entity_id in test_entities:
        hass.states.async_set(entity_id, STATE_ON)
        hass.states.async_set(entity_id, STATE_OFF)

    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {"id": 7, "type": "logbook/event_stream", "start_time": now.isoformat()}
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {"entity_id": "light.inc", "state": "off", "when": ANY},
        {"entity_id": "switch.any", "state": "off", "when": ANY},
        {"entity_id": "cover.included", "state": "off", "when": ANY},
    ]
    assert msg["event"]["start_time"] == now.timestamp()
    assert msg["event"]["end_time"] > msg["event"]["start_time"]
    assert msg["event"]["partial"] is True

    await hass.async_block_till_done()
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == []

    for entity_id in test_entities:
        hass.states.async_set(entity_id, STATE_ON)
        hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()

    hass.states.async_remove("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_set("light.zulu", "on", {"effect": "help", "color": "blue"})
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == [
        {"entity_id": "light.inc", "state": "on", "when": ANY},
        {"entity_id": "light.inc", "state": "off", "when": ANY},
        {"entity_id": "switch.any", "state": "on", "when": ANY},
        {"entity_id": "switch.any", "state": "off", "when": ANY},
        {"entity_id": "cover.included", "state": "on", "when": ANY},
        {"entity_id": "cover.included", "state": "off", "when": ANY},
    ]

    for _ in range(3):
        for entity_id in test_entities:
            hass.states.async_set(entity_id, STATE_ON)
            hass.states.async_set(entity_id, STATE_OFF)
        await async_wait_recording_done(hass)

        msg = await websocket_client.receive_json()
        assert msg["id"] == 7
        assert msg["type"] == "event"
        assert msg["event"]["events"] == [
            {"entity_id": "light.inc", "state": "on", "when": ANY},
            {"entity_id": "light.inc", "state": "off", "when": ANY},
            {"entity_id": "switch.any", "state": "on", "when": ANY},
            {"entity_id": "switch.any", "state": "off", "when": ANY},
            {"entity_id": "cover.included", "state": "on", "when": ANY},
            {"entity_id": "cover.included", "state": "off", "when": ANY},
        ]

    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: "cover.included"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: "cover.excluded"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {
            ATTR_NAME: "Mock automation switch matching entity",
            ATTR_ENTITY_ID: "switch.match_domain",
        },
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation switch matching domain", ATTR_DOMAIN: "switch"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation matches nothing"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: "light.inc"},
    )

    await hass.async_block_till_done()

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": "cover.included",
            "message": "triggered",
            "name": "Mock automation 3",
            "source": None,
            "when": ANY,
        },
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": "switch.match_domain",
            "message": "triggered",
            "name": "Mock automation switch matching entity",
            "source": None,
            "when": ANY,
        },
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": None,
            "message": "triggered",
            "name": "Mock automation switch matching domain",
            "source": None,
            "when": ANY,
        },
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": None,
            "message": "triggered",
            "name": "Mock automation matches nothing",
            "source": None,
            "when": ANY,
        },
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": "light.inc",
            "message": "triggered",
            "name": "Mock automation 3",
            "source": None,
            "when": ANY,
        },
    ]
    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_logbook_stream_excluded_entities_inherits_filters_from_recorder(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream inherits filters from recorder."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "automation", "script")
        ]
    )
    await async_setup_component(
        hass,
        logbook.DOMAIN,
        {
            logbook.DOMAIN: {
                CONF_EXCLUDE: {
                    CONF_ENTITIES: ["light.additional_excluded"],
                }
            },
            recorder.DOMAIN: {
                CONF_EXCLUDE: {
                    CONF_ENTITIES: ["light.exc"],
                    CONF_DOMAINS: ["switch"],
                    CONF_ENTITY_GLOBS: ["*.excluded", "*.no_matches"],
                }
            },
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("light.exc", STATE_ON)
    hass.states.async_set("light.exc", STATE_OFF)
    hass.states.async_set("switch.any", STATE_ON)
    hass.states.async_set("switch.any", STATE_OFF)
    hass.states.async_set("cover.excluded", STATE_ON)
    hass.states.async_set("cover.excluded", STATE_OFF)
    hass.states.async_set("light.additional_excluded", STATE_ON)
    hass.states.async_set("light.additional_excluded", STATE_OFF)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {"id": 7, "type": "logbook/event_stream", "start_time": now.isoformat()}
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]
    assert msg["event"]["start_time"] == now.timestamp()
    assert msg["event"]["end_time"] > msg["event"]["start_time"]
    assert msg["event"]["partial"] is True

    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == []

    hass.states.async_set("light.exc", STATE_ON)
    hass.states.async_set("light.exc", STATE_OFF)
    hass.states.async_set("switch.any", STATE_ON)
    hass.states.async_set("switch.any", STATE_OFF)
    hass.states.async_set("cover.excluded", STATE_ON)
    hass.states.async_set("cover.excluded", STATE_OFF)
    hass.states.async_set("light.additional_excluded", STATE_ON)
    hass.states.async_set("light.additional_excluded", STATE_OFF)
    hass.states.async_set("light.alpha", "on")
    hass.states.async_set("light.alpha", "off")
    alpha_off_state: State = hass.states.get("light.alpha")
    hass.states.async_set("light.zulu", "on", {"color": "blue"})
    hass.states.async_set("light.zulu", "off", {"effect": "help"})
    zulu_off_state: State = hass.states.get("light.zulu")
    hass.states.async_set(
        "light.zulu", "on", {"effect": "help", "color": ["blue", "green"]}
    )
    zulu_on_state: State = hass.states.get("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_remove("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_set("light.zulu", "on", {"effect": "help", "color": "blue"})
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == [
        {
            "entity_id": "light.alpha",
            "state": "off",
            "when": alpha_off_state.last_updated.timestamp(),
        },
        {
            "entity_id": "light.zulu",
            "state": "off",
            "when": zulu_off_state.last_updated.timestamp(),
        },
        {
            "entity_id": "light.zulu",
            "state": "on",
            "when": zulu_on_state.last_updated.timestamp(),
        },
    ]

    await async_wait_recording_done(hass)
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: "cover.excluded"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {
            ATTR_NAME: "Mock automation switch matching entity",
            ATTR_ENTITY_ID: "switch.match_domain",
        },
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation switch matching domain", ATTR_DOMAIN: "switch"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation matches nothing"},
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: "light.keep"},
    )
    hass.states.async_set("cover.excluded", STATE_ON)
    hass.states.async_set("cover.excluded", STATE_OFF)
    await hass.async_block_till_done()
    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": None,
            "message": "triggered",
            "name": "Mock automation matches nothing",
            "source": None,
            "when": ANY,
        },
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": "light.keep",
            "message": "triggered",
            "name": "Mock automation 3",
            "source": None,
            "when": ANY,
        },
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await hass.async_block_till_done()

    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {"id": 7, "type": "logbook/event_stream", "start_time": now.isoformat()}
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]
    assert msg["event"]["start_time"] == now.timestamp()
    assert msg["event"]["end_time"] > msg["event"]["start_time"]
    assert msg["event"]["partial"] is True

    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == []

    hass.states.async_set("light.alpha", "on")
    hass.states.async_set("light.alpha", "off")
    alpha_off_state: State = hass.states.get("light.alpha")
    hass.states.async_set("light.zulu", "on", {"color": "blue"})
    hass.states.async_set("light.zulu", "off", {"effect": "help"})
    zulu_off_state: State = hass.states.get("light.zulu")
    hass.states.async_set(
        "light.zulu", "on", {"effect": "help", "color": ["blue", "green"]}
    )
    zulu_on_state: State = hass.states.get("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_remove("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_set("light.zulu", "on", {"effect": "help", "color": "blue"})

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == [
        {
            "entity_id": "light.alpha",
            "state": "off",
            "when": alpha_off_state.last_updated.timestamp(),
        },
        {
            "entity_id": "light.zulu",
            "state": "off",
            "when": zulu_off_state.last_updated.timestamp(),
        },
        {
            "entity_id": "light.zulu",
            "state": "on",
            "when": zulu_on_state.last_updated.timestamp(),
        },
    ]

    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {
            ATTR_NAME: "Mock automation",
            ATTR_ENTITY_ID: "automation.mock_automation",
            ATTR_SOURCE: "numeric state of sensor.hungry_dogs",
        },
    )
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {
            ATTR_NAME: "Mock script",
            ATTR_ENTITY_ID: "script.mock_script",
            ATTR_SOURCE: "numeric state of sensor.hungry_dogs",
        },
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": "automation.mock_automation",
            "message": "triggered by numeric state of sensor.hungry_dogs",
            "name": "Mock automation",
            "source": "numeric state of sensor.hungry_dogs",
            "when": ANY,
        },
        {
            "context_id": ANY,
            "domain": "script",
            "entity_id": "script.mock_script",
            "message": "started",
            "name": "Mock script",
            "when": ANY,
        },
        {
            "domain": "homeassistant",
            "icon": "mdi:home-assistant",
            "message": "started",
            "name": "Home Assistant",
            "when": ANY,
        },
    ]

    context = core.Context(
        id="01GTDGKBCH00GW0X276W5TEDDD",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )
    automation_entity_id_test = "automation.alarm"
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {
            ATTR_NAME: "Mock automation",
            ATTR_ENTITY_ID: automation_entity_id_test,
            ATTR_SOURCE: "state of binary_sensor.dog_food_ready",
        },
        context=context,
    )
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {ATTR_NAME: "Mock script", ATTR_ENTITY_ID: "script.mock_script"},
        context=context,
    )
    hass.states.async_set(
        automation_entity_id_test,
        STATE_ON,
        {ATTR_FRIENDLY_NAME: "Alarm Automation"},
        context=context,
    )
    entity_id_test = "alarm_control_panel.area_001"
    hass.states.async_set(entity_id_test, STATE_OFF, context=context)
    hass.states.async_set(entity_id_test, STATE_ON, context=context)
    entity_id_second = "alarm_control_panel.area_002"
    hass.states.async_set(entity_id_second, STATE_OFF, context=context)
    hass.states.async_set(entity_id_second, STATE_ON, context=context)

    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "context_id": "01GTDGKBCH00GW0X276W5TEDDD",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "automation",
            "entity_id": "automation.alarm",
            "message": "triggered by state of binary_sensor.dog_food_ready",
            "name": "Mock automation",
            "source": "state of binary_sensor.dog_food_ready",
            "when": ANY,
        },
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_id": "01GTDGKBCH00GW0X276W5TEDDD",
            "context_message": "triggered by state of binary_sensor.dog_food_ready",
            "context_name": "Mock automation",
            "context_source": "state of binary_sensor.dog_food_ready",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "script",
            "entity_id": "script.mock_script",
            "message": "started",
            "name": "Mock script",
            "when": ANY,
        },
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_message": "triggered by state of binary_sensor.dog_food_ready",
            "context_name": "Mock automation",
            "context_source": "state of binary_sensor.dog_food_ready",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "entity_id": "alarm_control_panel.area_001",
            "state": "on",
            "when": ANY,
        },
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_message": "triggered by state of binary_sensor.dog_food_ready",
            "context_name": "Mock automation",
            "context_source": "state of binary_sensor.dog_food_ready",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "entity_id": "alarm_control_panel.area_002",
            "state": "on",
            "when": ANY,
        },
    ]
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 2", ATTR_ENTITY_ID: automation_entity_id_test},
        context=context,
    )

    await hass.async_block_till_done()

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_id": "01GTDGKBCH00GW0X276W5TEDDD",
            "context_message": "triggered by state of binary_sensor.dog_food_ready",
            "context_name": "Mock automation",
            "context_source": "state of binary_sensor.dog_food_ready",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "automation",
            "entity_id": "automation.alarm",
            "message": "triggered",
            "name": "Mock automation 2",
            "source": None,
            "when": ANY,
        }
    ]

    await async_wait_recording_done(hass)
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: automation_entity_id_test},
        context=context,
    )

    await hass.async_block_till_done()
    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_id": "01GTDGKBCH00GW0X276W5TEDDD",
            "context_message": "triggered by state of binary_sensor.dog_food_ready",
            "context_name": "Mock automation",
            "context_source": "state of binary_sensor.dog_food_ready",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "automation",
            "entity_id": "automation.alarm",
            "message": "triggered",
            "name": "Mock automation 3",
            "source": None,
            "when": ANY,
        }
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream_entities(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream with specific entities."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await hass.async_block_till_done()
    hass.states.async_set("light.small", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": ["light.small", "binary_sensor.is_light"],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "start_time" in msg["event"]
    assert "end_time" in msg["event"]
    assert msg["event"]["partial"] is True
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]

    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "start_time" in msg["event"]
    assert "end_time" in msg["event"]
    assert "partial" not in msg["event"]
    assert msg["event"]["events"] == []

    hass.states.async_set("light.alpha", STATE_ON)
    hass.states.async_set("light.alpha", STATE_OFF)
    hass.states.async_set("light.small", STATE_OFF, {"effect": "help", "color": "blue"})

    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]
    assert msg["event"]["events"] == [
        {
            "entity_id": "light.small",
            "state": "off",
            "when": ANY,
        },
    ]

    hass.states.async_remove("light.alpha")
    hass.states.async_remove("light.small")
    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream_entities_with_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream with specific entities and an end_time."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await hass.async_block_till_done()
    hass.states.async_set("light.small", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(minutes=10)).isoformat(),
            "entity_ids": ["light.small", "binary_sensor.is_light"],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["partial"] is True
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]

    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]
    assert msg["event"]["events"] == []

    hass.states.async_set("light.alpha", STATE_ON)
    hass.states.async_set("light.alpha", STATE_OFF)
    hass.states.async_set("light.small", STATE_OFF, {"effect": "help", "color": "blue"})

    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]
    assert msg["event"]["events"] == [
        {
            "entity_id": "light.small",
            "state": "off",
            "when": ANY,
        },
    ]

    hass.states.async_remove("light.alpha")
    hass.states.async_remove("light.small")
    await hass.async_block_till_done()

    async_fire_time_changed(hass, now + timedelta(minutes=11))
    await hass.async_block_till_done()

    # These states should not be sent since we should be unsubscribed
    hass.states.async_set("light.small", STATE_ON)
    hass.states.async_set("light.small", STATE_OFF)
    await hass.async_block_till_done()

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream_entities_past_only(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream with specific entities in the past."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await hass.async_block_till_done()
    hass.states.async_set("light.small", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "end_time": (dt_util.utcnow() - timedelta(microseconds=1)).isoformat(),
            "entity_ids": ["light.small", "binary_sensor.is_light"],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]

    # These states should not be sent since we should be unsubscribed
    # since we only asked for the past
    hass.states.async_set("light.small", STATE_ON)
    hass.states.async_set("light.small", STATE_OFF)
    await hass.async_block_till_done()

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream_big_query(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream and ask for a large time frame.

    We should get the data for the first 24 hours in the first message, and
    anything older will come in a followup message.
    """
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await hass.async_block_till_done()
    four_days_ago = now - timedelta(days=4)
    five_days_ago = now - timedelta(days=5)

    with freeze_time(four_days_ago):
        hass.states.async_set("binary_sensor.four_days_ago", STATE_ON)
        hass.states.async_set("binary_sensor.four_days_ago", STATE_OFF)
        four_day_old_state: State = hass.states.get("binary_sensor.four_days_ago")
        await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    # Verify our state was recorded in the past
    assert (now - four_day_old_state.last_updated).total_seconds() > 86400 * 3

    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    current_state: State = hass.states.get("binary_sensor.is_light")

    # Verify our new state was recorded in the recent timeframe
    assert (now - current_state.last_updated).total_seconds() < 2

    await async_wait_recording_done(hass)

    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": five_days_ago.isoformat(),
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # With a big query we get the current state first
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "on",
            "when": current_state.last_updated.timestamp(),
        }
    ]

    # With a big query we get the old states second
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["partial"] is True
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.four_days_ago",
            "state": "off",
            "when": four_day_old_state.last_updated.timestamp(),
        }
    ]

    # And finally a response without partial set to indicate no more
    # historical data is coming
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream_device(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test subscribe/unsubscribe logbook stream with a device."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    devices = await _async_mock_devices_with_logbook_platform(hass, device_registry)
    device = devices[0]
    device2 = devices[1]

    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "device_ids": [device.id, device2.id],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    await async_wait_recording_done(hass)

    # There are no answers to our initial query
    # so we get an empty reply. This is to ensure
    # consumers of the api know there are no results
    # and its not a failure case. This is useful
    # in the frontend so we can tell the user there
    # are no results vs waiting for them to appear
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []
    assert "partial" in msg["event"]
    await async_wait_recording_done(hass)

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []
    assert "partial" not in msg["event"]
    await async_wait_recording_done(hass)

    hass.states.async_set("binary_sensor.should_not_appear", STATE_ON)
    hass.states.async_set("binary_sensor.should_not_appear", STATE_OFF)
    hass.bus.async_fire("mock_event", {"device_id": device.id})
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {"domain": "test", "message": "is on fire", "name": "device name", "when": ANY}
    ]

    for _ in range(3):
        hass.bus.async_fire("mock_event", {"device_id": device.id})
        hass.bus.async_fire("mock_event", {"device_id": device2.id})
        await hass.async_block_till_done()

        msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
        assert msg["id"] == 7
        assert msg["type"] == "event"
        assert msg["event"]["events"] == [
            {
                "domain": "test",
                "message": "is on fire",
                "name": "device name",
                "when": ANY,
            },
            {
                "domain": "test",
                "message": "is on fire",
                "name": "device name",
                "when": ANY,
            },
        ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


async def test_event_stream_bad_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test event_stream bad start time."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/event_stream",
            "start_time": "cats",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_start_time"


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_logbook_stream_match_multiple_entities(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test logbook stream with a described integration that uses multiple entities."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    entry = await _async_mock_entity_with_logbook_platform(hass, entity_registry)
    entity_id = entry.entity_id
    hass.states.async_set(entity_id, STATE_ON)

    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": [entity_id],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # There are no answers to our initial query
    # so we get an empty reply. This is to ensure
    # consumers of the api know there are no results
    # and its not a failure case. This is useful
    # in the frontend so we can tell the user there
    # are no results vs waiting for them to appear
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []
    assert "partial" in msg["event"]
    await async_wait_recording_done(hass)

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []
    assert "partial" not in msg["event"]
    await async_wait_recording_done(hass)

    hass.states.async_set("binary_sensor.should_not_appear", STATE_ON)
    hass.states.async_set("binary_sensor.should_not_appear", STATE_OFF)
    context = core.Context(
        id="01GTDGKBCH00GW0X276W5TEDDD",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )
    hass.bus.async_fire(
        "mock_event", {"entity_id": ["sensor.any", entity_id]}, context=context
    )
    hass.bus.async_fire("mock_event", {"entity_id": [f"sensor.any,{entity_id}"]})
    hass.bus.async_fire("mock_event", {"entity_id": ["sensor.no_match", "light.off"]})
    hass.states.async_set(entity_id, STATE_OFF, context=context)
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "test",
            "message": "is on fire",
            "name": "device name",
            "when": ANY,
        },
        {
            "context_domain": "test",
            "context_event_type": "mock_event",
            "context_message": "is on fire",
            "context_name": "device name",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "entity_id": "sensor.test",
            "state": "off",
            "when": ANY,
        },
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_logbook_stream_match_multiple_entities_one_with_broken_logbook_platform(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logbook stream with a described integration that uses multiple entities.

    One of the entities has a broken logbook platform.
    """
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    entry = await _async_mock_entity_with_broken_logbook_platform(hass, entity_registry)
    entity_id = entry.entity_id
    hass.states.async_set(entity_id, STATE_ON)

    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": [entity_id],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # There are no answers to our initial query
    # so we get an empty reply. This is to ensure
    # consumers of the api know there are no results
    # and its not a failure case. This is useful
    # in the frontend so we can tell the user there
    # are no results vs waiting for them to appear
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []
    assert "partial" in msg["event"]
    await async_wait_recording_done(hass)

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []
    assert "partial" not in msg["event"]
    await async_wait_recording_done(hass)

    hass.states.async_set("binary_sensor.should_not_appear", STATE_ON)
    hass.states.async_set("binary_sensor.should_not_appear", STATE_OFF)
    context = core.Context(
        id="01GTDGKBCH00GW0X276W5TEDDD",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )
    hass.bus.async_fire(
        "mock_event", {"entity_id": ["sensor.any", entity_id]}, context=context
    )
    hass.bus.async_fire("mock_event", {"entity_id": [f"sensor.any,{entity_id}"]})
    hass.bus.async_fire("mock_event", {"entity_id": ["sensor.no_match", "light.off"]})
    hass.states.async_set(entity_id, STATE_OFF, context=context)
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "entity_id": "sensor.test",
            "context_domain": "test",
            "context_event_type": "mock_event",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "state": "off",
            "when": ANY,
        },
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)

    assert "Error with test describe event" in caplog.text


async def test_event_stream_bad_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test event_stream bad end time."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)
    utc_now = dt_util.utcnow()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/event_stream",
            "start_time": utc_now.isoformat(),
            "end_time": "cats",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"

    await client.send_json(
        {
            "id": 2,
            "type": "logbook/event_stream",
            "start_time": utc_now.isoformat(),
            "end_time": (utc_now - timedelta(hours=5)).isoformat(),
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"


async def test_live_stream_with_one_second_commit_interval(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the recorder with a 1s commit interval."""
    config = {recorder.CONF_COMMIT_INTERVAL: 0.5}
    await async_setup_recorder_instance(hass, config)
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    devices = await _async_mock_devices_with_logbook_platform(hass, device_registry)
    device = devices[0]

    await hass.async_block_till_done()

    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "1"})

    await async_wait_recording_done(hass)

    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "2"})

    await hass.async_block_till_done()

    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "3"})

    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "device_ids": [device.id],
        }
    )
    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "4"})

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "5"})

    recieved_rows = []
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    recieved_rows.extend(msg["event"]["events"])

    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "6"})

    await hass.async_block_till_done()

    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "7"})

    while len(recieved_rows) != 7:
        msg = await asyncio.wait_for(websocket_client.receive_json(), 2.5)
        assert msg["id"] == 7
        assert msg["type"] == "event"
        recieved_rows.extend(msg["event"]["events"])

    # Make sure we get rows back in order
    assert recieved_rows == [
        {"domain": "test", "message": "1", "name": "device name", "when": ANY},
        {"domain": "test", "message": "2", "name": "device name", "when": ANY},
        {"domain": "test", "message": "3", "name": "device name", "when": ANY},
        {"domain": "test", "message": "4", "name": "device name", "when": ANY},
        {"domain": "test", "message": "5", "name": "device name", "when": ANY},
        {"domain": "test", "message": "6", "name": "device name", "when": ANY},
        {"domain": "test", "message": "7", "name": "device name", "when": ANY},
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_disconnected(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream gets disconnected."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    await async_wait_recording_done(hass)

    hass.states.async_set("light.small", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    # We will compare event subscriptions after closing the websocket connection,
    # count the listeners before setting it up
    init_listeners = hass.bus.async_listeners()
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": ["light.small", "binary_sensor.is_light"],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]

    await websocket_client.close()
    await hass.async_block_till_done()

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_stream_consumer_stop_processing(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we unsubscribe if the stream consumer fails or is canceled."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    await async_wait_recording_done(hass)
    init_listeners = hass.bus.async_listeners()
    hass.states.async_set("light.small", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()

    after_ws_created_listeners = hass.bus.async_listeners()

    with patch.object(websocket_api, "MAX_PENDING_LOGBOOK_EVENTS", 5), patch.object(
        websocket_api, "_async_events_consumer"
    ):
        await websocket_client.send_json(
            {
                "id": 7,
                "type": "logbook/event_stream",
                "start_time": now.isoformat(),
                "entity_ids": ["light.small", "binary_sensor.is_light"],
            }
        )
        await async_wait_recording_done(hass)

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) != listeners_without_writes(init_listeners)
    for _ in range(5):
        hass.states.async_set("binary_sensor.is_light", STATE_ON)
        hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    await async_wait_recording_done(hass)

    # Check our listener got unsubscribed because
    # the queue got full and the overload safety tripped
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(after_ws_created_listeners)
    await websocket_client.close()
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_recorder_is_far_behind(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we still start live streaming if the recorder is far behind."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    await async_wait_recording_done(hass)
    devices = await _async_mock_devices_with_logbook_platform(hass, device_registry)
    device = devices[0]
    await async_wait_recording_done(hass)

    # Block the recorder queue
    await async_block_recorder(hass, 0.3)
    await hass.async_block_till_done()

    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "device_ids": [device.id],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # There are no answers to our initial query
    # so we get an empty reply. This is to ensure
    # consumers of the api know there are no results
    # and its not a failure case. This is useful
    # in the frontend so we can tell the user there
    # are no results vs waiting for them to appear
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []
    await async_wait_recording_done(hass)

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []

    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "1"})
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {"domain": "test", "message": "1", "name": "device name", "when": ANY}
    ]

    hass.bus.async_fire("mock_event", {"device_id": device.id, "message": "2"})
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {"domain": "test", "message": "2", "name": "device name", "when": ANY}
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_all_entities_are_continuous(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe/unsubscribe logbook stream with entities that are always filtered."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    await async_wait_recording_done(hass)
    entity_ids = ("sensor.uom", "sensor.uom_two")

    def _cycle_entities():
        for entity_id in entity_ids:
            for state in ("1", "2", "3"):
                hass.states.async_set(
                    entity_id, state, {ATTR_UNIT_OF_MEASUREMENT: "any"}
                )
                hass.states.async_set("counter.any", state)
                hass.states.async_set("proximity.any", state)

    # We will compare event subscriptions after closing the websocket connection,
    # count the listeners before setting it up
    init_listeners = hass.bus.async_listeners()
    _cycle_entities()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.uom", "counter.any", "proximity.any"],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    _cycle_entities()
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []

    await websocket_client.close()
    await hass.async_block_till_done()

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_all_entities_have_uom_multiple(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test logbook stream with specific request for multiple entities that are always filtered."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    await async_wait_recording_done(hass)
    entity_ids = ("sensor.uom", "sensor.uom_two")

    def _cycle_entities():
        for entity_id in entity_ids:
            for state in ("1", "2", "3"):
                hass.states.async_set(
                    entity_id, state, {ATTR_UNIT_OF_MEASUREMENT: "any"}
                )

    # We will compare event subscriptions after closing the websocket connection,
    # count the listeners before setting it up
    init_listeners = hass.bus.async_listeners()
    _cycle_entities()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": [*entity_ids],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    _cycle_entities()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []

    await websocket_client.close()
    await hass.async_block_till_done()

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_entities_some_have_uom_multiple(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test logbook stream with uom filtered entities and non-filtered entities."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    await async_wait_recording_done(hass)
    filtered_entity_ids = ("sensor.uom", "sensor.uom_two")
    non_filtered_entity_ids = ("sensor.keep", "sensor.keep_two")

    def _cycle_entities():
        for entity_id in filtered_entity_ids:
            for state in ("1", "2", "3"):
                hass.states.async_set(
                    entity_id, state, {ATTR_UNIT_OF_MEASUREMENT: "any"}
                )
        for entity_id in non_filtered_entity_ids:
            for state in (STATE_ON, STATE_OFF):
                hass.states.async_set(entity_id, state)

    # We will compare event subscriptions after closing the websocket connection,
    # count the listeners before setting it up
    init_listeners = hass.bus.async_listeners()
    _cycle_entities()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": [*filtered_entity_ids, *non_filtered_entity_ids],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {"entity_id": "sensor.keep", "state": "off", "when": ANY},
        {"entity_id": "sensor.keep_two", "state": "off", "when": ANY},
    ]
    assert msg["event"]["partial"] is True

    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]
    assert msg["event"]["events"] == []

    _cycle_entities()
    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()
    _cycle_entities()
    await get_instance(hass).async_block_till_done()
    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {"entity_id": "sensor.keep", "state": "on", "when": ANY},
        {"entity_id": "sensor.keep", "state": "off", "when": ANY},
        {"entity_id": "sensor.keep_two", "state": "on", "when": ANY},
        {"entity_id": "sensor.keep_two", "state": "off", "when": ANY},
    ]
    assert "partial" not in msg["event"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {"entity_id": "sensor.keep", "state": "on", "when": ANY},
        {"entity_id": "sensor.keep", "state": "off", "when": ANY},
        {"entity_id": "sensor.keep_two", "state": "on", "when": ANY},
        {"entity_id": "sensor.keep_two", "state": "off", "when": ANY},
    ]

    assert "partial" not in msg["event"]

    await websocket_client.close()
    await hass.async_block_till_done()

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_logbook_stream_ignores_forced_updates(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test logbook live stream ignores forced updates."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await hass.async_block_till_done()

    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await websocket_client.send_json(
        {"id": 7, "type": "logbook/event_stream", "start_time": now.isoformat()}
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]
    assert msg["event"]["start_time"] == now.timestamp()
    assert msg["event"]["end_time"] > msg["event"]["start_time"]
    assert msg["event"]["partial"] is True

    await hass.async_block_till_done()

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == []

    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": STATE_ON,
            "when": ANY,
        },
        {
            "entity_id": "binary_sensor.is_light",
            "state": STATE_OFF,
            "when": ANY,
        },
    ]

    # Now we force an update to make sure we ignore
    # forced updates when the state has not actually changed

    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    for _ in range(3):
        hass.states.async_set("binary_sensor.is_light", STATE_OFF, force_update=True)

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert "partial" not in msg["event"]["events"]
    assert msg["event"]["events"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": STATE_ON,
            "when": ANY,
        },
        # We should only get the first one and ignore
        # the other forced updates since the state
        # has not actually changed
        {
            "entity_id": "binary_sensor.is_light",
            "state": STATE_OFF,
            "when": ANY,
        },
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_all_entities_are_continuous_with_device(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test subscribe/unsubscribe logbook stream with entities that are always filtered and a device."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )
    await async_wait_recording_done(hass)
    devices = await _async_mock_devices_with_logbook_platform(hass, device_registry)
    device = devices[0]
    device2 = devices[1]

    entity_ids = ("sensor.uom", "sensor.uom_two")

    def _create_events():
        for entity_id in entity_ids:
            for state in ("1", "2", "3"):
                hass.states.async_set(
                    entity_id, state, {ATTR_UNIT_OF_MEASUREMENT: "any"}
                )
                hass.states.async_set("counter.any", state)
                hass.states.async_set("proximity.any", state)
        hass.bus.async_fire("mock_event", {"device_id": device.id})
        hass.bus.async_fire("mock_event", {"device_id": device2.id})

    # We will compare event subscriptions after closing the websocket connection,
    # count the listeners before setting it up
    init_listeners = hass.bus.async_listeners()
    _create_events()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.uom", "counter.any", "proximity.any"],
            "device_ids": [device.id, device2.id],
        }
    )

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == [
        {"domain": "test", "message": "is on fire", "name": "device name", "when": ANY},
        {"domain": "test", "message": "is on fire", "name": "device name", "when": ANY},
    ]
    assert msg["event"]["partial"] is True

    msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["events"] == []
    assert "partial" not in msg["event"]

    for _ in range(2):
        _create_events()
        msg = await asyncio.wait_for(websocket_client.receive_json(), 2)
        assert msg["id"] == 7
        assert msg["type"] == "event"
        assert msg["event"]["events"] == [
            {
                "domain": "test",
                "message": "is on fire",
                "name": "device name",
                "when": ANY,
            },
            {
                "domain": "test",
                "message": "is on fire",
                "name": "device name",
                "when": ANY,
            },
        ]
        assert "partial" not in msg["event"]

    await websocket_client.close()
    await hass.async_block_till_done()

    # Check our listener got unsubscribed
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)
