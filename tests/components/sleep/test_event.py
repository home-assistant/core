"""Test the Sleep as Android event platform."""

from http import HTTPStatus

from freezegun.api import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sleep.const import (
    ATTR_EVENT,
    ATTR_VALUE1,
    ATTR_VALUE2,
    ATTR_VALUE3,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
    ("entity", "event", "value1", "value2", "value3"),
    [
        ("sleep_tracking", "sleep_tracking_paused", None, None, None),
        ("sleep_tracking", "sleep_tracking_resumed", None, None, None),
        ("sleep_tracking", "sleep_tracking_started", None, None, None),
        ("sleep_tracking", "sleep_tracking_stopped", None, None, None),
        ("alarm_clock", "alarm_alert_dismiss", "1582719660934", "label", None),
        ("alarm_clock", "alarm_alert_start", "1582719660934", "label", None),
        ("alarm_clock", "alarm_rescheduled", None, None, None),
        ("alarm_clock", "alarm_skip_next", "1582719660934", "label", None),
        ("alarm_clock", "alarm_snooze_canceled", "1582719660934", "label", None),
        ("alarm_clock", "alarm_snooze_clicked", "1582719660934", "label", None),
        ("alarm_clock", "alarm_wake_up_check", None, None, None),
        ("alarm_clock", "before_smart_period", "label", None, None),
        ("alarm_clock", "show_skip_next_alarm", "1582719660934", "label", None),
        ("alarm_clock", "smart_period", None, None, None),
        ("alarm_clock", "time_to_bed_alarm_alert", "1582719660934", "label", None),
        ("anti_snoring", "antisnoring", None, None, None),
        ("sleep_apnea", "apnea_alarm", None, None, None),
        ("lullaby", "lullaby_start", None, None, None),
        ("lullaby", "lullaby_stop", None, None, None),
        ("lullaby", "lullaby_volume_down", None, None, None),
        ("sleep_phase", "awake", None, None, None),
        ("sleep_phase", "deep_sleep", None, None, None),
        ("sleep_phase", "light_sleep", None, None, None),
        ("sleep_phase", "not_awake", None, None, None),
        ("sleep_phase", "rem", None, None, None),
        ("sound_recognition", "sound_event_baby", None, None, None),
        ("sound_recognition", "sound_event_cough", None, None, None),
        ("sound_recognition", "sound_event_laugh", None, None, None),
        ("sound_recognition", "sound_event_snore", None, None, None),
        ("sound_recognition", "sound_event_talk", None, None, None),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@freeze_time("2025-01-01T03:30:00.000+00:00")
async def test_webhook_event(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    entity: str,
    event: str,
    value1: str | None,
    value2: str | None,
    value3: str | None,
) -> None:
    """Test webhook events."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get(f"event.sleep_as_android_{entity}"))
    assert state.state == STATE_UNKNOWN

    client = await hass_client_no_auth()
    payload = {ATTR_EVENT: event}
    if value1:
        payload[ATTR_VALUE1] = value1
    if value2:
        payload[ATTR_VALUE2] = value2
    if value3:
        payload[ATTR_VALUE3] = value3

    response = await client.post("/api/webhook/webhook_id", json=payload)
    assert response.status == HTTPStatus.NO_CONTENT

    assert (state := hass.states.get(f"event.sleep_as_android_{entity}"))
    assert state == snapshot


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
