"""The select tests for the tado platform."""

from collections.abc import Generator
from unittest.mock import patch

from PyTado.interface.api.my_tado import Timetable
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.tado import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TIMETABLE_SELECT_ENTITY = "select.baseboard_heater_schedule_days"


@pytest.fixture(autouse=True)
def setup_platforms() -> Generator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test creation of select entities."""

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("option", "expected_timetable"),
    [
        ("one_day", Timetable.ONE_DAY),
        ("three_day", Timetable.THREE_DAY),
        ("seven_day", Timetable.SEVEN_DAY),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_timetable(
    hass: HomeAssistant, option: str, expected_timetable: Timetable
) -> None:
    """Test selecting a timetable option."""

    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_timetable"
        ) as mock_set_timetable,
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.get_timetable",
            return_value=expected_timetable,
        ),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: TIMETABLE_SELECT_ENTITY, ATTR_OPTION: option},
            blocking=True,
        )

    mock_set_timetable.assert_called_once_with(1, expected_timetable)


@pytest.mark.usefixtures("init_integration")
async def test_select_entity_state(hass: HomeAssistant) -> None:
    """Test select entity has correct initial state."""

    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "seven_day"
    assert state.attributes.get("options") == ["one_day", "three_day", "seven_day"]


@pytest.mark.usefixtures("init_integration")
async def test_select_timetable_api_failure(hass: HomeAssistant) -> None:
    """Test selecting a timetable option when API fails."""

    with (
        patch(
            "homeassistant.components.tado.coordinator.TadoDataUpdateCoordinator.set_timetable",
            side_effect=HomeAssistantError("Error setting Tado timetable"),
        ),
        pytest.raises(HomeAssistantError) as exc,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: TIMETABLE_SELECT_ENTITY, ATTR_OPTION: "one_day"},
            blocking=True,
        )

    assert "Error setting Tado timetable" in str(exc.value)


@pytest.mark.usefixtures("init_integration")
async def test_select_entity_unavailable_when_no_timetable(
    hass: HomeAssistant,
) -> None:
    """Test select entity becomes unavailable when timetable data is None."""

    # Verify initial state is available
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "seven_day"

    # Get coordinator and update with None timetable data
    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = config_entry.runtime_data.coordinator

    # Set timetable to None for zone 1
    coordinator.data["timetable"] = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Verify entity is now unavailable
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_select_timetable_coordinator_refresh(hass: HomeAssistant) -> None:
    """Test that coordinator refresh is triggered after selecting a timetable."""

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = config_entry.runtime_data.coordinator

    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_timetable"
        ) as mock_set_timetable,
        patch.object(coordinator, "async_request_refresh") as mock_refresh,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: TIMETABLE_SELECT_ENTITY, ATTR_OPTION: "three_day"},
            blocking=True,
        )

    # Verify both the API call and the refresh were triggered
    mock_set_timetable.assert_called_once()
    mock_refresh.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_select_timetable_updates_state(hass: HomeAssistant) -> None:
    """Test that selecting a timetable option updates the entity state."""

    # Verify initial state
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "seven_day"

    # Select a different timetable option
    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_timetable"
        ) as mock_set_timetable,
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.get_timetable",
            return_value=Timetable.ONE_DAY,
        ),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: TIMETABLE_SELECT_ENTITY, ATTR_OPTION: "one_day"},
            blocking=True,
        )

    # Verify API was called
    mock_set_timetable.assert_called_once_with(1, Timetable.ONE_DAY)

    # Verify state was updated
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "one_day"
