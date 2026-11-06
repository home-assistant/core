"""Test the TFA.me integration: test of sensor.py."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.tfa_me.const import LOCAL_POLL_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import STATION_DATA_JSON

from tests.common import (
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    snapshot_platform,
)


async def test_tfa_me_sensor_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    tfa_me_config_entry: MockConfigEntry,
) -> None:
    """Snapshot all sensor entities created from a typical TFA.me JSON payload."""
    freezer.move_to("2025-11-26 15:12:00+00:00")
    entry = tfa_me_config_entry

    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(return_value=STATION_DATA_JSON),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_stale_sensor_value_returns_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tfa_me_config_entry: MockConfigEntry,
    mock_tfa_me_client: AsyncMock,
) -> None:
    """Test stale sensor values are reported as unavailable."""
    payload = {
        "gateway_id": "05B3E4E44",
        "sensors": [
            {
                "sensor_id": "a4481290f",
                "name": "A4481290F",
                "timestamp": "2025-11-26T15:10:42Z",
                "ts": "1764169842",
                "measurements": {
                    "temperature": {"value": "15.1", "unit": "°C"},
                },
            },
        ],
    }

    # A4 uses the 1-minute timeout class: 150 seconds.
    # Move well beyond that timestamp.
    freezer.move_to("2025-11-26 15:20:00+00:00")

    mock_tfa_me_client.return_value = payload

    assert await hass.config_entries.async_setup(tfa_me_config_entry.entry_id)
    await hass.async_block_till_done()

    temperature_state = hass.states.get(
        "sensor.tfa_me_a44_812_90f_05b3e4e44_temperature"
    )
    assert temperature_state is not None
    assert temperature_state.state == "unavailable"


async def test_new_measurement_added_once(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    tfa_me_config_entry: MockConfigEntry,
    mock_tfa_me_client: AsyncMock,
) -> None:
    """Test a newly discovered measurement is added only once."""
    freezer.move_to("2025-11-26 15:12:00+00:00")

    initial_payload = deepcopy(STATION_DATA_JSON)
    updated_payload = deepcopy(STATION_DATA_JSON)

    updated_payload["sensors"][0]["measurements"]["temperature"] = {
        "value": "15.1",
        "unit": "°C",
    }

    mock_tfa_me_client.side_effect = [
        initial_payload,
        updated_payload,
        updated_payload,
    ]

    assert await hass.config_entries.async_setup(tfa_me_config_entry.entry_id)
    await hass.async_block_till_done()

    before = {
        entry.entity_id
        for entry in entity_registry.entities.values()
        if entry.config_entry_id == tfa_me_config_entry.entry_id
    }

    # Trigger the first scheduled coordinator update.
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=LOCAL_POLL_INTERVAL),
    )
    await hass.async_block_till_done()

    after_first_refresh = {
        entry.entity_id
        for entry in entity_registry.entities.values()
        if entry.config_entry_id == tfa_me_config_entry.entry_id
    }

    assert len(after_first_refresh - before) == 1

    # Trigger another scheduled update with the same data.
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=2 * LOCAL_POLL_INTERVAL),
    )
    await hass.async_block_till_done()

    after_second_refresh = {
        entry.entity_id
        for entry in entity_registry.entities.values()
        if entry.config_entry_id == tfa_me_config_entry.entry_id
    }

    assert after_second_refresh == after_first_refresh
    assert mock_tfa_me_client.await_count == 3
