"""Test Ambient Weather Network sensors."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from aioambient import OpenAPI
from aioambient.errors import RequestError
from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform

from tests.common import async_fire_time_changed, snapshot_platform


@freeze_time("2023-11-9")
@pytest.mark.parametrize(
    "config_entry",
    ["AA:AA:AA:AA:AA:AA", "CC:CC:CC:CC:CC:CC", "DD:DD:DD:DD:DD:DD"],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    open_api: OpenAPI,
    aioambient: AsyncMock,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensors under normal operation."""
    await setup_platform(True, hass, config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("config_entry", ["BB:BB:BB:BB:BB:BB"], indirect=True)
async def test_sensors_with_no_data(
    hass: HomeAssistant,
    open_api: OpenAPI,
    aioambient: AsyncMock,
    config_entry: ConfigEntry,
) -> None:
    """Test that the sensors are not populated if the last data is absent."""
    await setup_platform(True, hass, config_entry)

    sensor = hass.states.get("sensor.station_b_temperature")
    assert sensor is not None
    assert "last_measured" not in sensor.attributes


@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_sensors_disappearing(
    hass: HomeAssistant,
    open_api: OpenAPI,
    aioambient: AsyncMock,
    config_entry: ConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we log errors properly."""

    initial_datetime = datetime(year=2023, month=11, day=8)
    with freeze_time(initial_datetime) as frozen_datetime:
        # Normal state, sensor is available.
        await setup_platform(True, hass, config_entry)
        sensor = hass.states.get("sensor.station_a_relative_pressure")
        assert sensor is not None
        assert float(sensor.state) == pytest.approx(1001.89694313129)

        # Sensor becomes unavailable if the network is unavailable. Log message
        # should only show up once.
        for _ in range(5):
            with patch.object(
                open_api, "get_device_details", side_effect=RequestError()
            ):
                frozen_datetime.tick(timedelta(minutes=10))
                async_fire_time_changed(hass)
                await hass.async_block_till_done()

            sensor = hass.states.get("sensor.station_a_relative_pressure")
            assert sensor is not None
            assert sensor.state == "unavailable"
            assert caplog.text.count("Cannot connect to Ambient Network") == 1

        # Network comes back. Sensor should start reporting again. Log message
        # should only show up once.
        for _ in range(5):
            frozen_datetime.tick(timedelta(minutes=10))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            sensor = hass.states.get("sensor.station_a_relative_pressure")
            assert sensor is not None
            assert float(sensor.state) == pytest.approx(1001.89694313129)
            assert caplog.text.count("Fetching ambient_network data recovered") == 1
