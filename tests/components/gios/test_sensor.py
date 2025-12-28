"""Test sensor of GIOS integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from gios import ApiError
from gios.model import GiosSensors
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gios.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.gios.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4"

    state = hass.states.get("sensor.home_pm2_5_index")
    assert state
    assert state.state == "good"

    state = hass.states.get("sensor.home_air_quality_index")
    assert state
    assert state.state == "good"


@pytest.mark.usefixtures("init_integration")
async def test_availability_api_error(
    hass: HomeAssistant,
    mock_gios: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4"

    mock_gios.async_update.side_effect = ApiError("Unexpected error")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_pm2_5_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_air_quality_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_gios.async_update.side_effect = None
    gios_sensors: GiosSensors = mock_gios.async_update.return_value
    old_pm25 = gios_sensors.pm25
    old_aqi = gios_sensors.aqi
    gios_sensors.pm25 = None
    gios_sensors.aqi = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # There is no PM2.5 data so the state should be unavailable
    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Indexes are empty so the state should be unavailable
    state = hass.states.get("sensor.home_air_quality_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Indexes are empty so the state should be unavailable
    state = hass.states.get("sensor.home_pm2_5_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    gios_sensors.pm25 = old_pm25
    gios_sensors.aqi = old_aqi

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4"

    state = hass.states.get("sensor.home_pm2_5_index")
    assert state
    assert state.state == "good"

    state = hass.states.get("sensor.home_air_quality_index")
    assert state
    assert state.state == "good"


async def test_dont_create_entities_when_data_missing_for_station(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gios: MagicMock,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_gios_sensors: GiosSensors,
) -> None:
    """Test that no entities are created when data is missing for the station."""
    mock_gios_sensors.co = None
    mock_gios_sensors.no = None
    mock_gios_sensors.no2 = None
    mock_gios_sensors.nox = None
    mock_gios_sensors.o3 = None
    mock_gios_sensors.pm10 = None
    mock_gios_sensors.pm25 = None
    mock_gios_sensors.so2 = None
    mock_gios_sensors.aqi = None
    mock_gios_sensors.c6h6 = None

    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_entity_ids() == []


async def test_missing_index_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gios: MagicMock,
    mock_gios_sensors: GiosSensors,
) -> None:
    """Test states of the sensor when API returns invalid indexes."""
    mock_gios_sensors.no2.index = None
    mock_gios_sensors.o3.index = None
    mock_gios_sensors.pm10.index = None
    mock_gios_sensors.pm25.index = None
    mock_gios_sensors.so2.index = None
    mock_gios_sensors.aqi = None

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.home_nitrogen_dioxide_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_ozone_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_pm10_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_pm2_5_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_sulphur_dioxide_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_air_quality_index")
    assert state is None


async def test_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_gios: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the unique_id migration."""
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "123-pm2.5",
        suggested_object_id="home_pm2_5",
        disabled_by=None,
    )

    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get("sensor.home_pm2_5")
    assert entry
    assert entry.unique_id == "123-pm25"
