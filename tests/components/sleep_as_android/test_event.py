"""Test the Sleep as Android event platform."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import patch

from freezegun.api import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def event_only() -> Generator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.sleep_as_android.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


@freeze_time("2025-01-01T03:30:00.000Z")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of event platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity", "payload"),
    [
        ("sleep_tracking", {"event": "sleep_tracking_paused"}),
        ("sleep_tracking", {"event": "sleep_tracking_resumed"}),
        ("sleep_tracking", {"event": "sleep_tracking_started"}),
        ("sleep_tracking", {"event": "sleep_tracking_stopped"}),
        (
            "alarm_clock",
            {
                "event": "alarm_alert_dismiss",
                "value1": "1582719660934",
                "value2": "label",
            },
        ),
        (
            "alarm_clock",
            {
                "event": "alarm_alert_start",
                "value1": "1582719660934",
                "value2": "label",
            },
        ),
        ("alarm_clock", {"event": "alarm_rescheduled"}),
        (
            "alarm_clock",
            {"event": "alarm_skip_next", "value1": "1582719660934", "value2": "label"},
        ),
        (
            "alarm_clock",
            {
                "event": "alarm_snooze_canceled",
                "value1": "1582719660934",
                "value2": "label",
            },
        ),
        (
            "alarm_clock",
            {
                "event": "alarm_snooze_clicked",
                "value1": "1582719660934",
                "value2": "label",
            },
        ),
        ("smart_wake_up", {"event": "before_smart_period", "value1": "label"}),
        ("smart_wake_up", {"event": "smart_period"}),
        ("sleep_health", {"event": "antisnoring"}),
        ("sleep_health", {"event": "apnea_alarm"}),
        ("lullaby", {"event": "lullaby_start"}),
        ("lullaby", {"event": "lullaby_stop"}),
        ("lullaby", {"event": "lullaby_volume_down"}),
        ("sleep_phase", {"event": "awake"}),
        ("sleep_phase", {"event": "deep_sleep"}),
        ("sleep_phase", {"event": "light_sleep"}),
        ("sleep_phase", {"event": "not_awake"}),
        ("sleep_phase", {"event": "rem"}),
        ("sound_recognition", {"event": "sound_event_baby"}),
        ("sound_recognition", {"event": "sound_event_cough"}),
        ("sound_recognition", {"event": "sound_event_laugh"}),
        ("sound_recognition", {"event": "sound_event_snore"}),
        ("sound_recognition", {"event": "sound_event_talk"}),
        ("user_notification", {"event": "alarm_wake_up_check"}),
        (
            "user_notification",
            {
                "event": "show_skip_next_alarm",
                "value1": "1582719660934",
                "value2": "label",
            },
        ),
        (
            "user_notification",
            {
                "event": "time_to_bed_alarm_alert",
                "value1": "1582719660934",
                "value2": "label",
            },
        ),
    ],
)
@freeze_time("2025-01-01T03:30:00.000+00:00")
async def test_webhook_event(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    entity: str,
    payload: dict[str, str],
) -> None:
    """Test webhook events."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get(f"event.sleep_as_android_{entity}"))
    assert state.state == STATE_UNKNOWN

    client = await hass_client_no_auth()

    response = await client.post("/api/webhook/webhook_id", json=payload)
    assert response.status == HTTPStatus.NO_CONTENT

    assert (state := hass.states.get(f"event.sleep_as_android_{entity}"))
    assert state.state == "2025-01-01T03:30:00.000+00:00"


async def test_webhook_invalid(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test webhook event call with invalid data."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client_no_auth()

    response = await client.post("/api/webhook/webhook_id", json={})

    assert response.status == HTTPStatus.UNPROCESSABLE_ENTITY
