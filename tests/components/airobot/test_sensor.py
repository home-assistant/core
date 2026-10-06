"""Tests for the Airobot sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from pyairobotmodbus.models import AirobotData as VUData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airobot.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.freeze_time("2024-01-01 00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_availability_without_optional_sensors(
    hass: HomeAssistant,
) -> None:
    """Test sensors are not created when optional hardware is not present."""
    # Default mock has no floor sensor, CO2, or AQI - they should not be created
    assert hass.states.get("sensor.test_thermostat_floor_temperature") is None
    assert hass.states.get("sensor.test_thermostat_carbon_dioxide") is None
    assert hass.states.get("sensor.test_thermostat_air_quality_index") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_vu_integration")
async def test_vu_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test the VU sensor entities."""
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_vu_config_entry.entry_id
    )


async def test_vu_sensors_without_extra_probe(
    hass: HomeAssistant,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
    mock_vu_data: VUData,
) -> None:
    """Test extra sensors are not created when the optional probe is absent."""
    mock_vu_client.async_get_data.return_value = replace(
        mock_vu_data, extra_temp=None, extra_humidity=None
    )
    mock_vu_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.airobot.VU_PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_vu_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.airobot_ventilation_extra_temperature") is None
    assert hass.states.get("sensor.airobot_ventilation_extra_humidity") is None
    # Non-optional sensors are still created
    assert hass.states.get("sensor.airobot_ventilation_supply_air_temperature")


@pytest.mark.parametrize(
    ("key", "enabled"),
    [
        pytest.param("supply_air_temperature", True, id="supply_air_temperature"),
        # Airflow is only measured on constant-flow models
        pytest.param("supply_airflow", False, id="supply_airflow"),
        pytest.param("extract_airflow", False, id="extract_airflow"),
    ],
)
@pytest.mark.usefixtures("init_vu_integration")
async def test_vu_sensor_enabled_by_default(
    entity_registry: er.EntityRegistry,
    mock_vu_config_entry: MockConfigEntry,
    key: str,
    enabled: bool,
) -> None:
    """Test which VU sensors are enabled by default."""
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{mock_vu_config_entry.unique_id}_{key}"
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert (entry.disabled_by is None) is enabled
