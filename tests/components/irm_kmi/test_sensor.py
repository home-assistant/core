"""Tests for the IRM KMI sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from irm_kmi_api import CurrentWeatherData, WarningData
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import (
    NEXT_WARNING_ENTITY_ID,
    TEMPERATURE_ENTITY_ID,
    WARNINGS,
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


@pytest.mark.parametrize(
    ("now", "warnings", "expected_state"),
    [
        pytest.param(
            "2023-12-28T15:30:00+01:00",
            WARNINGS,
            "2023-12-28T15:00:00+00:00",
            id="before_any_warning",
        ),
        pytest.param(
            "2023-12-28T18:00:00+01:00",
            WARNINGS,
            "2023-12-29T05:00:00+00:00",
            id="while_one_is_in_effect",
        ),
        pytest.param(
            "2023-12-29T06:00:00+01:00",
            WARNINGS,
            STATE_UNKNOWN,
            id="as_the_last_one_starts",
        ),
        pytest.param(
            "2023-12-29T13:00:00+01:00",
            WARNINGS,
            STATE_UNKNOWN,
            id="after_every_warning",
        ),
        pytest.param(
            "2023-12-28T15:30:00+01:00",
            [],
            STATE_UNKNOWN,
            id="without_any_warning",
        ),
    ],
)
async def test_next_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
    freezer: FrozenDateTimeFactory,
    now: str,
    warnings: list[WarningData],
    expected_state: str,
) -> None:
    """Test the sensor reports the start of the earliest upcoming warning."""
    freezer.move_to(now)
    mock_irm_kmi_api.get_warnings.return_value = warnings

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(NEXT_WARNING_ENTITY_ID)
    assert state
    assert state.state == expected_state
