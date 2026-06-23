"""Test the TFA.me integration: test of sensor.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"
# For snapshot: "pytest tests/components/tfa_me/test_sensor.py --snapshot-update"

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import naive_now

from .conftest import FAKE_JSON

from tests.common import AsyncMock, MockConfigEntry, SnapshotAssertion


def _stable_state_dict(data: dict) -> dict:
    """Return state dict without volatile fields."""
    data = dict(data)
    for key in ("last_changed", "last_updated", "last_reported", "context"):
        data.pop(key, None)
    return data


async def test_tfa_me_sensor_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    tfa_me_config_entry: MockConfigEntry,
) -> None:
    """Snapshot all sensor entities created from a typical TFA.me JSON payload."""

    freezer.move_to("2025-11-26 09:16:00+00:00")
    entry = tfa_me_config_entry
    entry.add_to_hass(hass)

    with pytest.MonkeyPatch.context() as monkeypatch:

        async def mock_async_get_sensors(*args, **kwargs):
            return FAKE_JSON

        monkeypatch.setattr(
            "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
            mock_async_get_sensors,
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    states: dict[str, dict] = {}

    for entity_id in sorted(hass.states.async_entity_ids("sensor")):
        registry_entry = ent_reg.async_get(entity_id)
        if registry_entry is None or registry_entry.config_entry_id != entry.entry_id:
            continue

        state = hass.states.get(entity_id)
        assert state is not None
        states[entity_id] = _stable_state_dict(state.as_dict())

    assert states == snapshot


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
    entry.add_to_hass(hass)

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

    ent_reg = er.async_get(hass)

    rain_states = {
        state.entity_id: state.state
        for state in hass.states.async_all("sensor")
        if "rain" in state.entity_id
    }

    rain_rel_state = None
    rain_1_hour_state = None
    rain_24_hours_state = None

    for entity_id in hass.states.async_entity_ids("sensor"):
        registry_entry = ent_reg.async_get(entity_id)
        if registry_entry is None:
            continue

        if registry_entry.unique_id.endswith("_rain_rel"):
            rain_rel_state = hass.states.get(entity_id)

        if registry_entry.unique_id.endswith("_rain_1_hour"):
            rain_1_hour_state = hass.states.get(entity_id)

        if registry_entry.unique_id.endswith("_rain_24_hours"):
            rain_24_hours_state = hass.states.get(entity_id)

    assert rain_rel_state is not None, f"Rain states: {rain_states}"
    assert rain_1_hour_state is not None, f"Rain states: {rain_states}"
    assert rain_24_hours_state is not None, f"Rain states: {rain_states}"

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
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(return_value=payload),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    temperature_state = None

    for entity_id in hass.states.async_entity_ids("sensor"):
        registry_entry = ent_reg.async_get(entity_id)
        if registry_entry is not None and registry_entry.unique_id.endswith(
            "_temperature"
        ):
            temperature_state = hass.states.get(entity_id)
            break

    assert temperature_state is not None
    assert temperature_state.state == STATE_UNKNOWN
