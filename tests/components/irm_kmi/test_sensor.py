"""Tests for the IRM KMI sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from irm_kmi_api import CurrentWeatherData
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import (
    TEMPERATURE_ENTITY_ID,
    WIND_DIRECTION_ENTITY_ID,
    WIND_GUST_SPEED_ENTITY_ID,
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Load only the sensor platform."""
    with patch("homeassistant.components.irm_kmi.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_irm_kmi_api")
@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the state of every sensor."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_irm_kmi_api")
async def test_wind_gust_speed_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the wind gust speed sensor is disabled by default."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(WIND_GUST_SPEED_ENTITY_ID) is None
    entity_entry = entity_registry.async_get(WIND_GUST_SPEED_ENTITY_ID)
    assert entity_entry
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.brussels_atmospheric_pressure",
        "sensor.brussels_uv_index",
        "sensor.brussels_wind_speed",
        WIND_DIRECTION_ENTITY_ID,
        WIND_GUST_SPEED_ENTITY_ID,
    ],
)
async def test_current_condition_sensor_without_its_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    entity_id: str,
) -> None:
    """Test a current condition the API leaves out is unknown."""
    mock_irm_kmi_api.get_current_weather.return_value = CurrentWeatherData(
        condition="cloudy", temperature=7.2
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "7.2"
