"""Tests for rainbird sensor platform."""

from http import HTTPStatus

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.rainbird.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    CONFIG_ENTRY_DATA_OLD_FORMAT,
    RAIN_DELAY,
    RAIN_DELAY_OFF,
    mock_response,
    mock_response_error,
)
from .test_calendar import SCHEDULE_RESPONSES

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMockResponse

PGM_A_NEXT_RUN = "sensor.rain_bird_controller_pgm_a_next_run"
PGM_B_NEXT_RUN = "sensor.rain_bird_controller_pgm_b_next_run"


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture(autouse=True)
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[Platform]:
    """Fixture to setup the config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("rain_delay_response", "expected_state"),
    [(RAIN_DELAY, "16"), (RAIN_DELAY_OFF, "0")],
)
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    expected_state: str,
) -> None:
    """Test sensor platform."""

    raindelay = hass.states.get("sensor.rain_bird_controller_raindelay")
    assert raindelay is not None
    assert raindelay.state == expected_state
    assert raindelay.attributes == {
        "friendly_name": "Rain Bird Controller Raindelay",
    }

    entity_entry = entity_registry.async_get("sensor.rain_bird_controller_raindelay")
    assert entity_entry
    assert entity_entry.unique_id == "4c:a1:61:00:11:22-raindelay"


async def test_program_next_run_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a disabled next run sensor is created for each program."""
    for program in ("a", "b", "c"):
        entity_id = f"sensor.rain_bird_controller_pgm_{program}_next_run"
        assert hass.states.get(entity_id) is None
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity_registry.async_get(PGM_A_NEXT_RUN).unique_id == (
        "4c:a1:61:00:11:22-program-0-next-run"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("setup_config_entry", [None])
async def test_program_next_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    responses: list[AiohttpClientMockResponse],
    config_entry: MockConfigEntry,
) -> None:
    """Test the next run sensor loads the schedule and follows each run."""
    await hass.config.async_set_time_zone("America/Regina")
    # Monday, 30 seconds before PGM A starts at 4:00 (10:00 UTC).
    freezer.move_to("2023-01-23 09:59:30")
    responses.extend(mock_response(response) for response in SCHEDULE_RESPONSES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    # PGM A runs Mondays and Tuesdays at 4:00, PGM B has no start times.
    state = hass.states.get(PGM_A_NEXT_RUN)
    assert state
    assert state.state == "2023-01-23T10:00:00+00:00"
    assert state.attributes["friendly_name"] == "Rain Bird Controller PGM A next run"
    assert hass.states.get(PGM_B_NEXT_RUN).state == STATE_UNKNOWN

    # Once the run starts, the sensor moves on to the following run.
    freezer.move_to("2023-01-23 10:00:01")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(PGM_A_NEXT_RUN).state == "2023-01-24T10:00:00+00:00"


@pytest.mark.parametrize(
    ("platforms", "setup_config_entry"), [([Platform.SENSOR, Platform.SWITCH], None)]
)
async def test_zone_run_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    responses: list[AiohttpClientMockResponse],
    config_entry: MockConfigEntry,
) -> None:
    """Test zone run time sensors from an earlier schedule load are added back."""
    zone_1, zone_6 = (
        entity_registry.async_get_or_create(
            Platform.SENSOR,
            DOMAIN,
            f"4c:a1:61:00:11:22-{zone}-program-0-run-time",
            config_entry=config_entry,
        ).entity_id
        for zone in (1, 6)
    )
    responses.extend(mock_response(response) for response in SCHEDULE_RESPONSES)

    # The enabled sensors load the schedule, with all other entities disabled.
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(zone_1)
    assert state
    assert state.state == "25"
    assert state.attributes["unit_of_measurement"] == "min"

    # PGM A does not water zone 6.
    assert hass.states.get(zone_6).state == "0"

    # A disabled sensor is added for each other zone PGM A waters.
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "4c:a1:61:00:11:22-2-program-0-run-time"
    )
    assert entity_id == "sensor.rain_bird_sprinkler_2_pgm_a_run_time"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("platforms", "setup_config_entry"),
    [([Platform.CALENDAR, Platform.SENSOR, Platform.SWITCH], None)],
)
async def test_zone_run_time_from_calendar(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    responses: list[AiohttpClientMockResponse],
    config_entry: MockConfigEntry,
) -> None:
    """Test zone run time sensors are added when the calendar loads the schedule."""
    responses.extend(mock_response(response) for response in SCHEDULE_RESPONSES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    # PGM A waters zones 1 to 5, the other programs have no zones.
    run_time_entries = sorted(
        entity_entry.entity_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity_entry.unique_id.endswith("-run-time")
    )
    assert run_time_entries == [
        f"sensor.rain_bird_sprinkler_{zone}_pgm_a_run_time" for zone in range(1, 6)
    ]
    assert all(
        entity_registry.async_get(entity_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
        for entity_id in run_time_entries
    )


@pytest.mark.parametrize(
    ("config_entry_unique_id", "config_entry_data", "setup_config_entry"),
    [
        # Config entry setup without a unique id since it had no serial number
        (
            None,
            {
                **CONFIG_ENTRY_DATA_OLD_FORMAT,
                "serial_number": 0,
            },
            None,
        ),
    ],
)
async def test_sensor_no_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    responses: list[AiohttpClientMockResponse],
    config_entry_unique_id: str | None,
    config_entry: MockConfigEntry,
) -> None:
    """Test sensor platform with no unique id."""

    # Failure to migrate config entry to a unique id
    responses.insert(1, mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE))

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    raindelay = hass.states.get("sensor.rain_bird_controller_raindelay")
    assert raindelay is not None
    assert raindelay.attributes.get("friendly_name") == "Rain Bird Controller Raindelay"

    entity_entry = entity_registry.async_get("sensor.rain_bird_controller_raindelay")
    assert (entity_entry is None) == (config_entry_unique_id is None)

    # Next run sensors are disabled by default, which needs a unique id.
    assert hass.states.get(PGM_A_NEXT_RUN) is None
