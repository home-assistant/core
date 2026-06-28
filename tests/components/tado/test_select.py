"""The select tests for the tado platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from PyTado.interface.api.my_tado import Timetable
import pytest
from requests import RequestException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.tado import DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

TIMETABLE_SELECT_ENTITY = "select.baseboard_heater_baseboard_heater_schedule_days"


@pytest.fixture(autouse=True)
def setup_platforms() -> Generator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SELECT]):
        yield


async def _enable_timetable_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    *entity_ids: str,
) -> None:
    """Enable timetable select entities and wait for the config entry reload."""
    for entity_id in entity_ids:
        entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("init_integration")
async def test_entity_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that timetable select entities are disabled by default.

    While disabled, the coordinator must not fetch timetable data, since that
    costs an additional API call per zone on every refresh.
    """
    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        assert entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(TIMETABLE_SELECT_ENTITY) is None
    assert config_entry.runtime_data.data["timetable"] == {}


@pytest.mark.usefixtures("init_integration")
async def test_timetable_only_fetched_when_enabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the timetable API is only called once an entity is enabled."""
    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(
        "homeassistant.components.tado.PyTado.interface.api.Tado.get_timetable"
    ) as mock_get_timetable:
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        mock_get_timetable.assert_not_called()

    await _enable_timetable_entities(hass, entity_registry, TIMETABLE_SELECT_ENTITY)

    with patch(
        "homeassistant.components.tado.PyTado.interface.api.Tado.get_timetable",
        return_value=Timetable.SEVEN_DAY,
    ) as mock_get_timetable:
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        mock_get_timetable.assert_called()


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test creation of select entities when enabled."""

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    all_entity_ids = [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
    ]
    await _enable_timetable_entities(hass, entity_registry, *all_entity_ids)

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
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    option: str,
    expected_timetable: Timetable,
) -> None:
    """Test selecting a timetable option."""
    await _enable_timetable_entities(hass, entity_registry, TIMETABLE_SELECT_ENTITY)

    # Verify initial state
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "seven_day"

    with patch(
        "homeassistant.components.tado.PyTado.interface.api.Tado.set_timetable"
    ) as mock_set_timetable:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: TIMETABLE_SELECT_ENTITY, ATTR_OPTION: option},
            blocking=True,
        )

    mock_set_timetable.assert_called_once_with(1, expected_timetable)

    # Verify state was updated
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == option


@pytest.mark.usefixtures("init_integration")
async def test_select_entity_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test select entity has correct initial state when enabled."""
    await _enable_timetable_entities(hass, entity_registry, TIMETABLE_SELECT_ENTITY)

    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "seven_day"
    assert state.attributes.get("options") == ["one_day", "three_day", "seven_day"]


@pytest.mark.usefixtures("init_integration")
async def test_select_timetable_api_failure(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test selecting a timetable option when API fails."""
    await _enable_timetable_entities(hass, entity_registry, TIMETABLE_SELECT_ENTITY)

    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_timetable",
            side_effect=RequestException("Boom"),
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
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select entity becomes unavailable when timetable data is missing."""
    await _enable_timetable_entities(hass, entity_registry, TIMETABLE_SELECT_ENTITY)

    # Verify initial state is available
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "seven_day"

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = config_entry.runtime_data

    coordinator.data["timetable"] = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_timetable_kept_on_update_failure(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test cached timetable data is kept and the entity stays available on API failure."""
    await _enable_timetable_entities(hass, entity_registry, TIMETABLE_SELECT_ENTITY)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = config_entry.runtime_data

    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "seven_day"
    cached_timetable = dict(coordinator.data["timetable"])

    with patch(
        "homeassistant.components.tado.PyTado.interface.api.Tado.get_timetable",
        side_effect=RequestException("Boom"),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert coordinator.data["timetable"] == cached_timetable
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "seven_day"


@pytest.mark.usefixtures("init_integration")
async def test_select_timetable_no_immediate_refresh(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the option is applied optimistically without an immediate full refresh."""
    await _enable_timetable_entities(hass, entity_registry, TIMETABLE_SELECT_ENTITY)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = config_entry.runtime_data

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

    # The API call is made, no full refresh is triggered, and the state reflects the
    # selected option immediately.
    mock_set_timetable.assert_called_once()
    mock_refresh.assert_not_called()
    state = hass.states.get(TIMETABLE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "three_day"
