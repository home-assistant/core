"""Test IntelliClima Sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyintelliclima import IntelliClimaDevices
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNKNOWN, Platform, UnitOfRatio
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_poll, setup_integration


@pytest.fixture(autouse=True)
async def setup_intelliclima_sensor_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
    mixed_eco_devices: IntelliClimaDevices,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the sensor platform."""
    mock_cloud_interface.get_all_device_status.return_value = mixed_eco_devices
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
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_family", "device_id", "entity_prefix", "gas_suffix"),
    [
        pytest.param(
            "ecocomfort2_devices",
            "56789",
            "sensor.test_vmc_",
            "volatile_organic_compounds_parts",
            id="eco2",
        ),
        pytest.param(
            "ecocomfort3_devices",
            "33333",
            "sensor.test_vmc_3_",
            "estimated_carbon_dioxide",
            id="eco3",
        ),
    ],
)
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
    mixed_eco_devices: IntelliClimaDevices,
    device_family: str,
    device_id: str,
    entity_prefix: str,
    gas_suffix: str,
    field: str,
    sentinel: str,
    entity_id: str,
) -> None:
    """Test a sensor reports unknown when the device sends its no-reading sentinel."""
    entity_id = entity_id.replace("sensor.test_vmc_", entity_prefix).replace(
        "volatile_organic_compounds_parts", gas_suffix
    )
    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNKNOWN

    setattr(getattr(mixed_eco_devices, device_family)[device_id], field, sentinel)
    await async_poll(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("co2", ["3427", "65535", None])
async def test_eco3_estimated_co2_uses_voc_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mixed_eco_devices: IntelliClimaDevices,
    co2: str | None,
) -> None:
    """Read eCO2 from voc_state regardless of the unrelated co2 register."""
    device = mixed_eco_devices.ecocomfort3_devices["33333"]
    device.voc_state = "850"
    device.co2 = co2
    await async_poll(hass, freezer)

    assert (state := hass.states.get("sensor.test_vmc_3_estimated_carbon_dioxide"))
    assert state.state == "850.0"
    assert state.attributes["device_class"] == SensorDeviceClass.CO2
    assert state.attributes["unit_of_measurement"] == UnitOfRatio.PARTS_PER_MILLION
    assert hass.states.get("sensor.test_vmc_3_volatile_organic_compounds_parts") is None
    assert (voc := hass.states.get("sensor.test_vmc_volatile_organic_compounds_parts"))
    assert voc.state == "89.0"
    assert (
        voc.attributes["device_class"]
        == SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
    )
