"""Test Enphase Envoy time platform."""

from datetime import time
from unittest.mock import AsyncMock, patch

from pyenphase.exceptions import EnvoyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

GENERATOR_EXERCISE_START_ENTITY = "time.generator_1234_exercise_start_time"


@pytest.mark.parametrize("mock_envoy", ["envoy_metered_batt_relay"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_time(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test time platform entities against snapshot."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_envoy",
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_eu_batt",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=True,
)
async def test_no_time(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test time platform entities are not created."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, config_entry)
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)


@pytest.mark.parametrize("mock_envoy", ["envoy_metered_batt_relay"], indirect=True)
@pytest.mark.parametrize(
    ("test_value", "expected_minutes"),
    [
        pytest.param(time(0, 0), 0, id="midnight"),
        pytest.param(time(6, 45), 405, id="quarter_to_seven"),
        pytest.param(time(23, 59), 1439, id="last_minute"),
    ],
)
async def test_time_operation_generator_exercise_start(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    test_value: time,
    expected_minutes: int,
) -> None:
    """Test the standby generator exercise start time entity operation."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, config_entry)

    # the fixture has the exercise starting 810 minutes after midnight
    assert (entity_state := hass.states.get(GENERATOR_EXERCISE_START_ENTITY))
    assert entity_state.state == "13:30:00"

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: GENERATOR_EXERCISE_START_ENTITY,
            ATTR_TIME: test_value,
        },
        blocking=True,
    )

    mock_envoy.update_generator_schedule.assert_awaited_once_with(
        {"exercise_start": expected_minutes}, refresh=True
    )


@pytest.mark.parametrize("mock_envoy", ["envoy_metered_batt_relay"], indirect=True)
async def test_time_operation_generator_exercise_start_with_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the generator exercise start time entity with error returned."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, config_entry)

    mock_envoy.update_generator_schedule.side_effect = EnvoyError("Test")
    with pytest.raises(
        HomeAssistantError,
        match=(
            "Failed to execute async_set_value for "
            f"{GENERATOR_EXERCISE_START_ENTITY}, host"
        ),
    ):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: GENERATOR_EXERCISE_START_ENTITY,
                ATTR_TIME: time(6, 45),
            },
            blocking=True,
        )


@pytest.mark.parametrize("mock_envoy", ["envoy_metered_batt_relay"], indirect=True)
async def test_no_time_generator_exercise_start(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the exercise start time entity is not created without a schedule."""
    mock_envoy.data.generator_schedule = None
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, config_entry)

    assert hass.states.get(GENERATOR_EXERCISE_START_ENTITY) is None
