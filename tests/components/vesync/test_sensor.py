"""Tests for the sensor module."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vesync.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_HUMIDIFIER_HUMIDITY, mock_devices_response


@pytest.mark.freeze_time("2026-11-16 12:00:00+00:00")
@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_sensor_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(aioclient_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == SENSOR_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("cook_status", "expected_state"),
    [
        pytest.param(None, "unknown", id="missing"),
        pytest.param("appointing", "appointing", id="appointing"),
    ],
)
async def test_cook_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    cook_status: str | None,
    expected_state: str,
) -> None:
    """Test cook status values supported by the integration."""
    mock_devices_response(
        aioclient_mock,
        "CS158-AF Air Fryer Cooking",
        details_override={"cookStatus": cook_status},
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.cs158_af_air_fryer_cooking_cooking_status")
    assert state is not None
    assert state.state == expected_state


@pytest.mark.freeze_time("2026-11-16 12:00:00.400+00:00")
@pytest.mark.parametrize(
    ("device_name", "entity_id", "expected_state"),
    [
        pytest.param(
            "Dual Air Fryer",
            "sensor.dual_air_fryer_basket_1_cooking_end",
            "2026-11-16T12:19:00+00:00",
            id="dual_cooking",
        ),
        pytest.param(
            "Dual Air Fryer",
            "sensor.dual_air_fryer_basket_2_cooking_end",
            "unknown",
            id="dual_standby",
        ),
        pytest.param(
            "CS158-AF Air Fryer Cooking",
            "sensor.cs158_af_air_fryer_cooking_cooking_end",
            "2026-11-16T12:10:00+00:00",
            id="single_cooking",
        ),
        pytest.param(
            "CS158-AF Air Fryer Standby",
            "sensor.cs158_af_air_fryer_standby_cooking_end",
            "unknown",
            id="single_standby",
        ),
    ],
)
async def test_cook_end_time(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test the cook end time is the last update plus the remaining time."""
    mock_devices_response(aioclient_mock, device_name)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.freeze_time("2026-11-16 12:00:00.400+00:00")
async def test_cook_end_time_across_updates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the cook end time across updates: kept, moved, unknown when paused, fresh on resume."""
    device_name = "CS158-AF Air Fryer Cooking"
    entity_id = "sensor.cs158_af_air_fryer_cooking_cooking_end"
    mock_devices_response(aioclient_mock, device_name)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2026-11-16T12:10:00+00:00"
    last_changed = state.last_changed

    async def refresh(minutes_left: int, status: str = "cooking") -> State | None:
        """Poll the fryer 61 s later: a minute less drifts the estimate by 1 s."""
        aioclient_mock.clear_requests()
        mock_devices_response(
            aioclient_mock,
            device_name,
            details_override={"cookLastTime": minutes_left, "cookStatus": status},
        )
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        return hass.states.get(entity_id)

    # Each poll a minute less: the drift is ignored, no new state.
    for minutes_left in (9, 8, 7, 6):
        state = await refresh(minutes_left)
        assert state is not None
        assert state.state == "2026-11-16T12:10:00+00:00"
        assert state.last_changed == last_changed

    # The countdown slips by a minute, then by two: the end time moves.
    state = await refresh(6)
    assert state is not None
    assert state.state == "2026-11-16T12:10:00+00:00"
    state = await refresh(6)
    assert state is not None
    assert state.state == "2026-11-16T12:12:06+00:00"

    # Paused: unknown, as the end time keeps moving while paused.
    state = await refresh(6, "cookStop")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Resumed: a fresh end time, although within the variance of the last one.
    state = await refresh(5)
    assert state is not None
    assert state.state == "2026-11-16T12:13:08+00:00"


async def test_humidity(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of humidity sensor entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_HUMIDITY).state == "35"
