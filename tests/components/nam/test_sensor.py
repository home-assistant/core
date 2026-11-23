"""Test sensor of Nettigo Air Monitor integration."""

from dataclasses import replace
from unittest.mock import MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from nettigo_air_monitor import ApiError, InvalidSensorDataError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from tenacity import RetryError

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.nam.const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import NAM_SENSORS


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_nam_client")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the air_quality."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2024-04-20 12:00:00+00:00")

    with patch("homeassistant.components.nam.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_nam_client")
async def test_sensor_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor disabled by default."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get("sensor.nettigo_air_monitor_signal_strength")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-signal"
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, disabled_by=None
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False


async def test_incomplete_data_after_device_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nam_client: MagicMock,
) -> None:
    """Test states of the air_quality after device restart."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == "7.95"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    mock_nam_client.async_update.return_value = replace(
        NAM_SENSORS, heca_temperature=None
    )
    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exc",
    [
        ApiError("API Error"),
        InvalidSensorDataError("Invalid sensor data"),
        RetryError(Mock()),
        TimeoutError,
    ],
)
async def test_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nam_client: MagicMock,
    exc: Exception | type[Exception],
) -> None:
    """Ensure we mark entities unavailable when device causes an error."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "7.56"

    mock_nam_client.async_update.side_effect = exc
    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_nam_client.async_update.side_effect = None
    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "7.56"


async def test_manual_update_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nam_client: MagicMock,
) -> None:
    """Test manual update entity via service homeasasistant/update_entity."""
    await setup_integration(hass, mock_config_entry)

    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    mock_nam_client.async_update.reset_mock()
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.nettigo_air_monitor_bme280_temperature"]},
        blocking=True,
    )

    assert mock_nam_client.async_update.call_count == 1


@pytest.mark.usefixtures("mock_nam_client")
async def test_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the unique_id migration."""
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-temperature",
        suggested_object_id="nettigo_air_monitor_dht22_temperature",
        disabled_by=None,
    )

    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-humidity",
        suggested_object_id="nettigo_air_monitor_dht22_humidity",
        disabled_by=None,
    )

    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get("sensor.nettigo_air_monitor_dht22_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-dht22_temperature"

    entry = entity_registry.async_get("sensor.nettigo_air_monitor_dht22_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-dht22_humidity"
