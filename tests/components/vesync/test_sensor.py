"""Tests for the sensor module."""

from datetime import UTC, datetime

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vesync.sensor import _get_cook_end_time
from homeassistant.core import HomeAssistant
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
async def test_cook_end_time_stable_between_updates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the cook end time does not move while the remaining time counts down."""
    mock_devices_response(aioclient_mock, "Dual Air Fryer")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    fryer = next(iter(config_entry.runtime_data.manager.devices))
    end_time = datetime(2026, 11, 16, 12, 19, tzinfo=UTC)
    assert _get_cook_end_time(fryer.state_chamber_1) == end_time

    # 45 s later, before the next update, the remaining time has counted down.
    freezer.tick(45.3)
    assert fryer.state_chamber_1.total_time_remaining == 1095
    assert _get_cook_end_time(fryer.state_chamber_1) == end_time


async def test_humidity(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of humidity sensor entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_HUMIDITY).state == "35"
