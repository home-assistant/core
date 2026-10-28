"""Tests for the sensor module."""

from types import SimpleNamespace

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.vesync.sensor import SENSORS
from homeassistant.const import EntityCategory, UnitOfRatio, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_HUMIDIFIER_HUMIDITY, mock_devices_response


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


async def test_humidity(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of humidity sensor entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_HUMIDITY).state == "35"


@pytest.mark.parametrize(
    ("key", "attribute", "value", "device_class", "unit", "category"),
    [
        ("eleva-aqi", "aqi", 20, SensorDeviceClass.AQI, None, None),
        (
            "eleva-carbon-filter-life",
            "carbon_filter_life",
            95,
            None,
            UnitOfRatio.PERCENTAGE,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "eleva-pre-filter-life",
            "pre_filter_life",
            90,
            None,
            UnitOfRatio.PERCENTAGE,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "eleva-filter-remaining-days",
            "filter_remain_day",
            720,
            None,
            UnitOfTime.DAYS,
            EntityCategory.DIAGNOSTIC,
        ),
    ],
)
def test_eleva_300x_sensor_descriptions(
    key, attribute, value, device_class, unit, category
) -> None:
    """Test Eleva 300X sensor values and availability."""
    description = next(sensor for sensor in SENSORS if sensor.key == key)

    eleva = SimpleNamespace(
        device_type="LAP-C341S-WEU",
        state=SimpleNamespace(**{attribute: value}),
    )
    other = SimpleNamespace(
        device_type="LAP-V102S-AAS",
        state=SimpleNamespace(**{attribute: value}),
    )

    assert description.exists_fn(eleva)
    assert description.value_fn(eleva) == value
    assert not description.exists_fn(other)
    assert description.device_class == device_class
    assert description.native_unit_of_measurement == unit
    assert description.entity_category == category
    assert description.state_class == SensorStateClass.MEASUREMENT

    missing = SimpleNamespace(
        device_type="LAP-C341S-WEU",
        state=SimpleNamespace(**{attribute: None}),
    )
    assert not description.exists_fn(missing)
