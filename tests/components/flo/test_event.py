"""Test Flo by Moen event entities."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from aioflo.errors import RequestError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)

from homeassistant.components.flo.const import DOMAIN
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback

ENTITY_ID = "event.smart_water_shutoff_alert"


async def _poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    alarm_counts: list[dict[str, Any]],
    is_connected: bool = True,
) -> None:
    """Advance to the next poll with the valve reporting the given pending alarms."""
    valve = await async_load_json_object_fixture(
        hass, "device_info_response.json", DOMAIN
    )
    valve["notifications"]["pending"]["alarmCount"] = alarm_counts
    valve["isConnected"] = is_connected
    detector = await async_load_json_object_fixture(
        hass, "device_info_response_detector.json", DOMAIN
    )

    async def get_info(device_id: str) -> dict[str, Any]:
        return valve if device_id == "98765" else detector

    with patch("aioflo.device.Device.get_info", side_effect=get_info):
        freezer.tick(timedelta(seconds=65))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


@pytest.fixture
async def fired(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> list[dict[str, Any]]:
    """Set up the integration and collect the alert events it fires."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    events: list[dict[str, Any]] = []

    last_fired: str | None = None

    @callback
    def record(event: Event[EventStateChangedData]) -> None:
        nonlocal last_fired
        new_state = event.data["new_state"]
        if (
            event.data["entity_id"] == ENTITY_ID
            and new_state is not None
            and new_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and new_state.state != last_fired
        ):
            last_fired = new_state.state
            events.append(dict(new_state.attributes))

    hass.bus.async_listen(EVENT_STATE_CHANGED, record)
    return events


async def test_pending_alerts_at_startup_do_not_fire(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, fired: list[dict[str, Any]]
) -> None:
    """Test alerts already pending at startup are not reported as new."""
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    # The fixture's two pending warnings, unchanged.
    await _poll(
        hass,
        freezer,
        [
            {"id": 30, "severity": "warning", "count": 1},
            {"id": 31, "severity": "warning", "count": 1},
        ],
    )

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
    assert fired == []


@pytest.mark.parametrize(
    ("alarm_counts", "expected"),
    [
        pytest.param(
            [
                {"id": 30, "severity": "warning", "count": 1},
                {"id": 31, "severity": "warning", "count": 1},
                {"id": 53, "severity": "critical", "count": 1},
            ],
            [("critical", 53, 1)],
            id="new_alert_while_others_pending",
        ),
        pytest.param(
            [
                {"id": 30, "severity": "warning", "count": 2},
                {"id": 31, "severity": "warning", "count": 1},
            ],
            [("warning", 30, 2)],
            id="pending_alert_occurs_again",
        ),
        pytest.param(
            [
                {"id": 30, "severity": "warning", "count": 1},
                {"id": 31, "severity": "warning", "count": 1},
                {"id": 28, "severity": "info", "count": 1},
                {"id": 53, "severity": "critical", "count": 1},
            ],
            [("info", 28, 1), ("critical", 53, 1)],
            id="two_new_alerts_in_one_poll",
        ),
        pytest.param(
            [
                {"id": 30, "severity": "warning", "count": 1},
                {"id": 31, "severity": "warning", "count": 1},
                {"id": 99, "severity": "unexpected", "count": 1},
            ],
            [("info", 99, 1)],
            id="unknown_severity_reported_as_info",
        ),
        pytest.param(
            [{"id": 30, "severity": "warning", "count": 1}],
            [],
            id="dismissed_alert_does_not_fire",
        ),
    ],
)
async def test_new_alerts_fire(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fired: list[dict[str, Any]],
    alarm_counts: list[dict[str, Any]],
    expected: list[tuple[str, int, int]],
) -> None:
    """Test each new alert fires once, even while older ones are pending."""
    await _poll(hass, freezer, alarm_counts)

    assert [
        (event["event_type"], event["alarm_id"], event["count"]) for event in fired
    ] == expected


async def test_dismissed_alert_fires_when_raised_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, fired: list[dict[str, Any]]
) -> None:
    """Test an alert fires again after it was dismissed and then re-raised."""
    await _poll(
        hass,
        freezer,
        [
            {"id": 30, "severity": "warning", "count": 2},
            {"id": 31, "severity": "warning", "count": 1},
        ],
    )
    await _poll(hass, freezer, [{"id": 31, "severity": "warning", "count": 1}])
    await _poll(
        hass,
        freezer,
        [
            {"id": 30, "severity": "warning", "count": 1},
            {"id": 31, "severity": "warning", "count": 1},
        ],
    )

    assert [(event["alarm_id"], event["count"]) for event in fired] == [
        (30, 2),
        (30, 1),
    ]


async def test_lower_count_does_not_fire(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, fired: list[dict[str, Any]]
) -> None:
    """Test a pending alert whose count drops is not reported as new."""
    await _poll(
        hass,
        freezer,
        [
            {"id": 30, "severity": "warning", "count": 2},
            {"id": 31, "severity": "warning", "count": 1},
        ],
    )
    await _poll(
        hass,
        freezer,
        [
            {"id": 30, "severity": "warning", "count": 1},
            {"id": 31, "severity": "warning", "count": 1},
        ],
    )

    assert [(event["alarm_id"], event["count"]) for event in fired] == [(30, 2)]


async def test_alert_fires_after_coordinator_recovers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, fired: list[dict[str, Any]]
) -> None:
    """Test alerts seen as the coordinator fails are each reported on recovery."""
    pending = [
        {"id": 30, "severity": "warning", "count": 1},
        {"id": 31, "severity": "warning", "count": 1},
    ]
    new_alerts = [
        *pending,
        {"id": 28, "severity": "warning", "count": 1},
        {"id": 53, "severity": "critical", "count": 1},
    ]
    with patch("aioflo.water.Water.get_consumption_info", side_effect=RequestError):
        # Three failures are buffered; the fourth marks the coordinator failed
        # after the device info, with the new alerts, was already fetched.
        for _ in range(3):
            await _poll(hass, freezer, pending)
        await _poll(hass, freezer, new_alerts)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert fired == []

    await _poll(hass, freezer, new_alerts)

    assert [(event["event_type"], event["alarm_id"]) for event in fired] == [
        ("warning", 28),
        ("critical", 53),
    ]


async def test_alert_fires_while_device_offline(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, fired: list[dict[str, Any]]
) -> None:
    """Test alerts about a disconnected device are still reported."""
    await _poll(
        hass,
        freezer,
        [
            {"id": 30, "severity": "warning", "count": 1},
            {"id": 31, "severity": "warning", "count": 1},
            {"id": 33, "severity": "critical", "count": 1},
        ],
        is_connected=False,
    )

    assert [(event["event_type"], event["alarm_id"]) for event in fired] == [
        ("critical", 33)
    ]
    assert (
        hass.states.get("sensor.smart_water_shutoff_water_pressure").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("fired")
async def test_no_event_for_leak_detectors(hass: HomeAssistant) -> None:
    """Test leak detectors do not get an alert event entity."""
    assert hass.states.async_entity_ids("event") == [ENTITY_ID]
