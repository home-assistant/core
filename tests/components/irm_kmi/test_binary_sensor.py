"""Tests for the IRM KMI binary sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.irm_kmi.const import CONF_LANGUAGE_OVERRIDE
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import WARNING_ENTITY_ID


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Load only the binary sensor platform."""
    with patch("homeassistant.components.irm_kmi.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.freeze_time("2023-12-28T18:00:00+01:00")
@pytest.mark.usefixtures("mock_irm_kmi_api")
async def test_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the warning binary sensor while one of two warnings is in effect."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("now", "expected_state"),
    [
        pytest.param("2023-12-28T15:59:59+01:00", STATE_OFF, id="before_the_warning"),
        pytest.param("2023-12-28T16:00:00+01:00", STATE_ON, id="as_it_starts"),
        pytest.param("2023-12-28T18:00:00+01:00", STATE_ON, id="during_the_warning"),
        pytest.param("2023-12-28T20:00:00+01:00", STATE_OFF, id="as_it_ends"),
        pytest.param("2023-12-28T20:00:01+01:00", STATE_OFF, id="after_the_warning"),
        pytest.param("2023-12-29T09:00:00+01:00", STATE_ON, id="during_the_next_one"),
    ],
)
@pytest.mark.usefixtures("mock_irm_kmi_api")
async def test_warning_is_on_within_its_window_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    now: str,
    expected_state: str,
) -> None:
    """Test the sensor is on strictly between the start and the end of a warning."""
    freezer.move_to(now)

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(WARNING_ENTITY_ID)
    assert state
    assert state.state == expected_state


async def test_warning_without_any_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: MagicMock,
) -> None:
    """Test the sensor is off without warnings."""
    mock_irm_kmi_api.get_warnings.return_value = []

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(WARNING_ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes["warnings"] == []


@pytest.mark.usefixtures("mock_get_forecasts_coord")
@pytest.mark.parametrize("forecast_fixture", ["antwerp_with_heat_warning.json"])
@pytest.mark.freeze_time("2025-06-18T18:40:00+02:00")
async def test_warning_from_a_recorded_forecast(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a warning of a recorded forecast."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(WARNING_ENTITY_ID) == snapshot


@pytest.mark.usefixtures("mock_get_forecasts_coord")
@pytest.mark.parametrize("forecast_fixture", ["antwerp_with_heat_warning.json"])
@pytest.mark.parametrize(
    ("hass_language", "options", "expected_name"),
    [
        pytest.param("en", {}, "Heat", id="english"),
        pytest.param("en", {CONF_LANGUAGE_OVERRIDE: "fr"}, "Chaleur", id="override_fr"),
        pytest.param("en", {CONF_LANGUAGE_OVERRIDE: "nl"}, "Hitte", id="override_nl"),
        pytest.param("nl", {}, "Hitte", id="follow_home_assistant"),
    ],
)
@pytest.mark.freeze_time("2025-06-18T18:40:00+02:00")
async def test_warning_language(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_language: str,
    options: dict[str, str],
    expected_name: str,
) -> None:
    """Test the warning text is fetched in the language the user asked for."""
    hass.config.language = hass_language
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(WARNING_ENTITY_ID)
    assert state
    assert state.attributes["warnings"][0]["friendly_name"] == expected_name
