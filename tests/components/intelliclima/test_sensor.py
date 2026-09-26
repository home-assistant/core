"""Test IntelliClima Sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyintelliclima import IntelliClimaDevices
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import async_poll, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def setup_intelliclima_sensor_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the sensor platform."""
    with (
        patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)
        # Let tests run against this initialized state
        yield


async def test_all_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # There should be exactly three sensor entities
    sensor_entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "intelliclima" and entry.domain == SENSOR_DOMAIN
    ]
    assert len(sensor_entries) == 3

    entity_entry = sensor_entries[0]
    # Device should exist and match snapshot
    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("field", "sentinel", "entity_id"),
    [
        pytest.param("tamb", "327.67", "sensor.test_vmc_temperature", id="temperature"),
        pytest.param("rh", "143", "sensor.test_vmc_humidity", id="humidity"),
        pytest.param(
            "voc_state",
            "65535",
            "sensor.test_vmc_volatile_organic_compounds_parts",
            id="voc",
        ),
    ],
)
async def test_sensor_no_reading(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    single_eco_device: IntelliClimaDevices,
    field: str,
    sentinel: str,
    entity_id: str,
) -> None:
    """Test a sensor reports unknown when the device sends its no-reading sentinel."""
    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNKNOWN

    setattr(single_eco_device.ecocomfort2_devices["56789"], field, sentinel)
    await async_poll(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN
