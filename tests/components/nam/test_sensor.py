"""Test sensor of Nettigo Air Monitor integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from nettigo_air_monitor import ApiError
from syrupy import SnapshotAssertion

from homeassistant.components.nam.const import DOMAIN
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
from homeassistant.util.dt import utcnow

from . import INCOMPLETE_NAM_DATA, init_integration

from tests.common import (
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)


async def test_sensor(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test states of the air_quality."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2024-04-20 12:00:00+00:00")

    with patch("homeassistant.components.nam.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_disabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test sensor disabled by default."""
    await init_integration(hass)

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


async def test_incompleta_data_after_device_restart(hass: HomeAssistant) -> None:
    """Test states of the air_quality after device restart."""
    await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == "8.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    future = utcnow() + timedelta(minutes=6)
    update_response = Mock(json=AsyncMock(return_value=INCOMPLETE_NAM_DATA))
    with (
        patch("homeassistant.components.nam.NettigoAirMonitor.initialize"),
        patch(
            "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
            return_value=update_response,
        ),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when device causes an error."""
    nam_data = load_json_object_fixture("nam/nam_data.json")

    await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "7.6"

    future = utcnow() + timedelta(minutes=6)
    with (
        patch("homeassistant.components.nam.NettigoAirMonitor.initialize"),
        patch(
            "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
            side_effect=ApiError("API Error"),
        ),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=12)
    update_response = Mock(json=AsyncMock(return_value=nam_data))
    with (
        patch("homeassistant.components.nam.NettigoAirMonitor.initialize"),
        patch(
            "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
            return_value=update_response,
        ),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "7.6"


async def test_manual_update_entity(hass: HomeAssistant) -> None:
    """Test manual update entity via service homeasasistant/update_entity."""
    nam_data = load_json_object_fixture("nam/nam_data.json")

    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})

    update_response = Mock(json=AsyncMock(return_value=nam_data))
    with (
        patch("homeassistant.components.nam.NettigoAirMonitor.initialize"),
        patch(
            "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
            return_value=update_response,
        ) as mock_get_data,
    ):
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.nettigo_air_monitor_bme280_temperature"]},
            blocking=True,
        )

    assert mock_get_data.call_count == 1


async def test_unique_id_migration(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
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

    await init_integration(hass)

    entry = entity_registry.async_get("sensor.nettigo_air_monitor_dht22_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-dht22_temperature"

    entry = entity_registry.async_get("sensor.nettigo_air_monitor_dht22_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-dht22_humidity"
