"""Test Ambient Weather Network sensors."""

from datetime import datetime, timedelta
from unittest.mock import patch

from aioambient import OpenAPI
from aioambient.errors import RequestError
from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform

from tests.common import async_fire_time_changed, snapshot_platform


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    open_api: OpenAPI,
    aioambient,
    config_entry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensors under normal operation."""
    await setup_platform(True, hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@freeze_time("2023-11-09")
@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_sensors_with_stale_data(
    hass: HomeAssistant, open_api: OpenAPI, aioambient, config_entry
) -> None:
    """Test that the sensors are not populated if the data is stale."""
    await setup_platform(False, hass, config_entry)

    sensor = hass.states.get("sensor.station_a_absolute_pressure")
    assert sensor is None


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["BB:BB:BB:BB:BB:BB"], indirect=True)
async def test_sensors_with_no_data(
    hass: HomeAssistant, open_api: OpenAPI, aioambient, config_entry
) -> None:
    """Test that the sensors are not populated if the last data is absent."""
    await setup_platform(False, hass, config_entry)

    sensor = hass.states.get("sensor.station_b_absolute_pressure")
    assert sensor is None


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["CC:CC:CC:CC:CC:CC"], indirect=True)
async def test_sensors_with_no_update_time(
    hass: HomeAssistant, open_api: OpenAPI, aioambient, config_entry
) -> None:
    """Test that the sensors are not populated if the update time is missing."""
    await setup_platform(False, hass, config_entry)

    sensor = hass.states.get("sensor.station_c_absolute_pressure")
    assert sensor is None


@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_sensors_disappearing(
    hass: HomeAssistant,
    open_api: OpenAPI,
    aioambient,
    config_entry,
    caplog,
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
