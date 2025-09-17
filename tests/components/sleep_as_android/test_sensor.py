"""Test the Sleep as Android sensor platform."""

from collections.abc import Generator
from datetime import datetime
from http import HTTPStatus
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.sleep_as_android.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of sensor platform."""

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "sensor.sleep_as_android_next_alarm",
                    "",
                ),
                {
                    "native_value": datetime.fromisoformat("2020-02-26T12:21:00+00:00"),
                    "native_unit_of_measurement": None,
                },
            ),
            (
                State(
                    "sensor.sleep_as_android_alarm_label",
                    "",
                ),
                {
                    "native_value": "label",
                    "native_unit_of_measurement": None,
                },
            ),
        ),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "event",
    [
        "alarm_snooze_clicked",
        "alarm_snooze_canceled",
        "alarm_alert_start",
        "alarm_alert_dismiss",
        "alarm_skip_next",
        "show_skip_next_alarm",
        "alarm_rescheduled",
    ],
)
async def test_webhook_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    event: str,
) -> None:
    """Test webhook updates sensor."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("sensor.sleep_as_android_next_alarm"))
    assert state.state == STATE_UNKNOWN

    assert (state := hass.states.get("sensor.sleep_as_android_alarm_label"))
    assert state.state == STATE_UNKNOWN

    client = await hass_client_no_auth()

    response = await client.post(
        "/api/webhook/webhook_id",
        json={
            "event": event,
            "value1": "1582719660934",
            "value2": "label",
        },
    )
    assert response.status == HTTPStatus.NO_CONTENT

    assert (state := hass.states.get("sensor.sleep_as_android_next_alarm"))
    assert state.state == "2020-02-26T12:21:00+00:00"

    assert (state := hass.states.get("sensor.sleep_as_android_alarm_label"))
    assert state.state == "label"


async def test_webhook_sensor_alarm_unset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test unsetting sensors if there is no next alarm."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client_no_auth()

    response = await client.post(
        "/api/webhook/webhook_id",
        json={
            "event": "alarm_rescheduled",
            "value1": "1582719660934",
            "value2": "label",
        },
    )
    assert response.status == HTTPStatus.NO_CONTENT

    assert (state := hass.states.get("sensor.sleep_as_android_next_alarm"))
    assert state.state == "2020-02-26T12:21:00+00:00"

    assert (state := hass.states.get("sensor.sleep_as_android_alarm_label"))
    assert state.state == "label"

    response = await client.post(
        "/api/webhook/webhook_id",
        json={"event": "alarm_rescheduled"},
    )
    assert (state := hass.states.get("sensor.sleep_as_android_next_alarm"))
    assert state.state == STATE_UNKNOWN

    assert (state := hass.states.get("sensor.sleep_as_android_alarm_label"))
    assert state.state == STATE_UNKNOWN
