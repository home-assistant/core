"""Tests for the ALLNET sensor platform."""

from allnet.models import Channel, ChannelKind
import pytest

from homeassistant.components.allnet.const import DOMAIN
from homeassistant.components.allnet.sensor import (
    AllnetSensorEntity,
    _pm_device_class,
    _resolve_mapping,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    UnitOfElectricCurrent,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_UNIQUE_ID


@pytest.mark.asyncio
async def test_sensor_entities_created(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that sensor entities are created for SENSOR channels."""
    # temp_0, current_0, humidity_0 (all kind=SENSOR)
    state_temp = hass.states.get("sensor.allnet_test_device_temperature")
    state_current = hass.states.get("sensor.allnet_test_device_current")
    state_humidity = hass.states.get("sensor.allnet_test_device_humidity")

    assert state_temp is not None
    assert state_current is not None
    assert state_humidity is not None


@pytest.mark.asyncio
async def test_sensor_native_value(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that sensor native_value is set from channel.value."""
    state = hass.states.get("sensor.allnet_test_device_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(22.5)


@pytest.mark.asyncio
async def test_sensor_temperature_device_class(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that °C unit maps to TEMPERATURE device class."""
    state = hass.states.get("sensor.allnet_test_device_temperature")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS


@pytest.mark.asyncio
async def test_sensor_current_device_class(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that A unit maps to CURRENT device class."""
    state = hass.states.get("sensor.allnet_test_device_current")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.CURRENT
    assert state.attributes.get("unit_of_measurement") == UnitOfElectricCurrent.AMPERE


@pytest.mark.asyncio
async def test_sensor_humidity_device_class(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that % unit maps to HUMIDITY device class."""
    state = hass.states.get("sensor.allnet_test_device_humidity")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_sensor_unavailable_when_value_none(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that sensors with value=None are marked unavailable."""
    state = hass.states.get("sensor.allnet_test_device_humidity")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_sensor_unique_id(
    hass: HomeAssistant,
    setup_integration: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensor entities have the correct unique_id."""
    entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{TEST_UNIQUE_ID}_temp_0_sensor"
    )
    assert entry is not None


@pytest.mark.asyncio
async def test_sensor_no_binary_sensors_in_sensor_platform(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that binary_sensor channels don't appear as sensor entities."""
    state = hass.states.get("sensor.allnet_test_device_door_contact")
    assert state is None


@pytest.mark.parametrize(
    ("name", "expected_device_class"),
    [
        pytest.param("PM10", SensorDeviceClass.PM10, id="pm10"),
        pytest.param("PM2.5", SensorDeviceClass.PM25, id="pm25"),
        pytest.param("PM4", SensorDeviceClass.PM4, id="pm4"),
        pytest.param("PM1", SensorDeviceClass.PM1, id="pm1"),
        pytest.param("Particles", None, id="unknown"),
    ],
)
def test_pm_device_class(
    name: str, expected_device_class: SensorDeviceClass | None
) -> None:
    """Test particulate matter sensor device class mappings."""
    assert _pm_device_class(name) is expected_device_class


def test_sensor_mapping_for_particulate_matter_and_unknown_unit() -> None:
    """Test sensor mappings for particulate matter and unknown units."""
    pm_mapping = _resolve_mapping(
        Channel(
            id="pm25",
            kind=ChannelKind.SENSOR,
            name="PM2.5",
            value=10,
            unit="µg/m³",
            raw={},
        )
    )
    unknown_mapping = _resolve_mapping(
        Channel(
            id="unknown",
            kind=ChannelKind.SENSOR,
            name="Unknown",
            value=1,
            unit="custom",
            raw={},
        )
    )

    assert pm_mapping.device_class is SensorDeviceClass.PM25
    assert unknown_mapping.device_class is None
    assert unknown_mapping.unit == "custom"


@pytest.mark.asyncio
async def test_sensor_without_channel_has_no_native_value(
    setup_integration: ConfigEntry,
) -> None:
    """Test a sensor without a channel returns no native value."""
    runtime = setup_integration.runtime_data
    entity = AllnetSensorEntity(
        runtime.coordinator,
        "missing",
        runtime.ha_device_info,
        "unique_id",
        "Missing channel",
        None,
        None,
        None,
    )

    assert entity.native_value is None
