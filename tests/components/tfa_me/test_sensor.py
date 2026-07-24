"""Test the TFA.me integration: test of sensor.py."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import naive_now

from .conftest import FAKE_JSON

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    SnapshotAssertion,
    snapshot_platform,
)


async def test_tfa_me_sensor_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    tfa_me_config_entry: MockConfigEntry,
) -> None:
    """Snapshot all sensor entities created from a typical TFA.me JSON payload."""
    freezer.move_to("2025-11-26 09:16:00+00:00")
    entry = tfa_me_config_entry

    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(return_value=FAKE_JSON),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_rain_history_updates_on_coordinator_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tfa_me_config_entry: MockConfigEntry,
) -> None:
    """Test rain history sensors update after coordinator refresh."""
    freezer.move_to("2025-11-26 15:00:00+00:00")
    ts_1 = int(naive_now().timestamp())

    freezer.move_to("2025-11-26 15:30:00+00:00")
    ts_2 = int(naive_now().timestamp())

    def rain_payload(value: str, ts: int) -> dict:
        return {
            "gateway_id": "05B3E4E44",
            "sensors": [
                {
                    "sensor_id": "a1fffffea",
                    "name": "A1FFFFFEA",
                    "timestamp": "2025-11-26T15:00:00Z",
                    "ts": str(ts),
                    "measurements": {
                        "rssi": {"value": "192", "unit": "/255"},
                        "lowbatt": {"value": "0", "unit": ""},
                        "rain": {"value": value, "unit": "mm"},
                    },
                },
            ],
        }

    entry = tfa_me_config_entry

    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(
            side_effect=[
                rain_payload("7.4", ts_1),
                rain_payload("8.9", ts_2),
            ]
        ),
    ):
        freezer.move_to("2025-11-26 15:00:00+00:00")
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        freezer.move_to("2025-11-26 15:30:00+00:00")
        await entry.runtime_data.async_request_refresh()
        await hass.async_block_till_done()

    rain_rel_state = hass.states.get(
        "sensor.tfa_me_a1f_fff_fea_05b3e4e44_relative_rain"
    )
    rain_1_hour_state = hass.states.get(
        "sensor.tfa_me_a1f_fff_fea_05b3e4e44_rain_last_hour"
    )
    rain_24_hours_state = hass.states.get(
        "sensor.tfa_me_a1f_fff_fea_05b3e4e44_rain_last_24_hours"
    )

    assert rain_rel_state is not None
    assert rain_1_hour_state is not None
    assert rain_24_hours_state is not None

    assert rain_rel_state.state == "1.5"
    assert rain_1_hour_state.state == "1.5"
    assert rain_24_hours_state.state == "1.5"


async def test_invalid_measurement_value_returns_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tfa_me_config_entry: MockConfigEntry,
) -> None:
    """Test invalid measurement value results in unknown state."""
    freezer.move_to("2025-11-26 15:15:00+00:00")
    ts = int(naive_now().timestamp())

    payload = {
        "gateway_id": "05B3E4E44",
        "sensors": [
            {
                "sensor_id": "a4481290f",
                "name": "A4481290F",
                "timestamp": "2025-11-26T15:10:42Z",
                "ts": str(ts),
                "measurements": {
                    "temperature": {"value": "NOT_A_NUMBER", "unit": "°C"},
                },
            },
        ],
    }

    entry = tfa_me_config_entry

    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(return_value=payload),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    temperature_state = hass.states.get(
        "sensor.tfa_me_a44_812_90f_05b3e4e44_temperature"
    )

    assert temperature_state is not None
    assert temperature_state.state == STATE_UNKNOWN


async def test_stale_sensor_value_returns_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tfa_me_config_entry: MockConfigEntry,
) -> None:
    """Test stale sensor values are reported as unknown."""
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

    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(return_value=payload),
    ):
        assert await hass.config_entries.async_setup(tfa_me_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    temperature_state = None
    for entity_id in hass.states.async_entity_ids("sensor"):
        registry_entry = entity_registry.async_get(entity_id)
        if registry_entry is not None and registry_entry.unique_id.endswith(
            "_temperature"
        ):
            temperature_state = hass.states.get(entity_id)
            break

    assert temperature_state is not None
    assert temperature_state.state == "unknown"
