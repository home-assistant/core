"""Tests for the SleepIQ integration."""

from collections.abc import Callable
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, create_autospec

from asyncsleepiq import (
    Side,
    SleepData,
    SleepIQAPIException,
    SleepIQBed,
    SleepIQFoundation,
    SleepIQLoginException,
    SleepIQSleeper,
    SleepIQTimeoutException,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.sleepiq.const import DOMAIN, IS_IN_BED, SLEEP_NUMBER
from homeassistant.components.sleepiq.coordinator import (
    LONGER_UPDATE_INTERVAL,
    SLEEP_DATA_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_USERNAME, PRESSURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import (
    BED_ID,
    SLEEPER_L_ID,
    SLEEPER_L_NAME,
    SLEEPER_L_NAME_LOWER,
    SLEEPER_R_ID,
    SLEEPER_R_NAME,
    SLEEPIQ_CONFIG,
    setup_platform,
)

from tests.common import (
    MockConfigEntry,
    RegistryEntryWithDefaults,
    async_fire_time_changed,
    mock_registry,
)

ENTITY_IS_IN_BED = f"sensor.sleepnumber_{BED_ID}_{SLEEPER_L_NAME_LOWER}_{IS_IN_BED}"
ENTITY_PRESSURE = f"sensor.sleepnumber_{BED_ID}_{SLEEPER_L_NAME_LOWER}_{PRESSURE}"
ENTITY_SLEEP_NUMBER = (
    f"sensor.sleepnumber_{BED_ID}_{SLEEPER_L_NAME_LOWER}_{SLEEP_NUMBER}"
)


async def test_unload_entry(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test unloading the SleepIQ entry."""
    entry = await setup_platform(hass, "sensor")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_entry_setup_login_error(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client is unable to login."""
    mock_asyncsleepiq.login.side_effect = SleepIQLoginException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_entry_setup_timeout_error(
    hass: HomeAssistant, mock_asyncsleepiq
) -> None:
    """Test when sleepiq client timeout."""
    mock_asyncsleepiq.login.side_effect = SleepIQTimeoutException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_update_interval(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test update interval."""
    await setup_platform(hass, "sensor")
    assert mock_asyncsleepiq.fetch_bed_statuses.call_count == 1

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert mock_asyncsleepiq.fetch_bed_statuses.call_count == 2


async def test_api_error(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client is unable to login."""
    mock_asyncsleepiq.init_beds.side_effect = SleepIQAPIException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_api_timeout(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client timeout."""
    mock_asyncsleepiq.init_beds.side_effect = SleepIQTimeoutException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


@pytest.mark.parametrize(
    ("get_fetch_mock", "platform", "interval"),
    [
        pytest.param(
            lambda client, bed: client.fetch_bed_statuses,
            "sensor",
            UPDATE_INTERVAL,
            id="bed_status",
        ),
        pytest.param(
            lambda client, bed: bed.fetch_pause_mode,
            "switch",
            LONGER_UPDATE_INTERVAL,
            id="pause_mode",
        ),
        pytest.param(
            lambda client, bed: bed.sleepers[0].fetch_sleep_data,
            "sensor",
            SLEEP_DATA_UPDATE_INTERVAL,
            id="sleep_data",
        ),
    ],
)
async def test_update_auth_error_starts_reauth_flow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_asyncsleepiq: MagicMock,
    mock_bed: MagicMock,
    get_fetch_mock: Callable[[MagicMock, MagicMock], MagicMock],
    platform: str,
    interval: timedelta,
) -> None:
    """Test an authentication failure during an update starts the reauth flow."""
    entry = await setup_platform(hass, platform)

    get_fetch_mock(mock_asyncsleepiq, mock_bed).side_effect = SleepIQAPIException(
        HTTPStatus.UNAUTHORIZED, "unauthorized"
    )
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_update_api_error_does_not_start_reauth_flow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_asyncsleepiq: MagicMock,
) -> None:
    """Test a non-authentication API error during an update does not start reauth."""
    await setup_platform(hass, "sensor")

    mock_asyncsleepiq.fetch_bed_statuses.side_effect = SleepIQAPIException(
        HTTPStatus.INTERNAL_SERVER_ERROR, "server error"
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_asyncsleepiq.fetch_bed_statuses.call_count == 2
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_unique_id_migration(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test migration of sensor unique IDs."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=SLEEPIQ_CONFIG,
        unique_id=SLEEPIQ_CONFIG[CONF_USERNAME].lower(),
    )

    mock_entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            ENTITY_IS_IN_BED: RegistryEntryWithDefaults(
                entity_id=ENTITY_IS_IN_BED,
                unique_id=f"{BED_ID}_{SLEEPER_L_NAME}_{IS_IN_BED}",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            ENTITY_PRESSURE: RegistryEntryWithDefaults(
                entity_id=ENTITY_PRESSURE,
                unique_id=f"{BED_ID}_{SLEEPER_L_NAME}_{PRESSURE}",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            ENTITY_SLEEP_NUMBER: RegistryEntryWithDefaults(
                entity_id=ENTITY_SLEEP_NUMBER,
                unique_id=f"{BED_ID}_{SLEEPER_L_NAME}_{SLEEP_NUMBER}",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)  # pylint: disable=home-assistant-tests-registry-fixtures

    sensor_is_in_bed = ent_reg.async_get(ENTITY_IS_IN_BED)
    assert sensor_is_in_bed.unique_id == f"{SLEEPER_L_ID}_{IS_IN_BED}"

    sensor_pressure = ent_reg.async_get(ENTITY_PRESSURE)
    assert sensor_pressure.unique_id == f"{SLEEPER_L_ID}_{PRESSURE}"

    sensor_sleep_number = ent_reg.async_get(ENTITY_SLEEP_NUMBER)
    assert sensor_sleep_number.unique_id == f"{SLEEPER_L_ID}_{SLEEP_NUMBER}"


def _make_controller() -> MagicMock:
    """Build a bare controller bed with no foundation features."""
    controller = create_autospec(SleepIQBed)
    controller.name = "Firmness Control"
    controller.id = "ctrl_001"
    controller.mac_addr = "AA:BB:CC:DD:EE:01"
    controller.model = "Firmness Control, 360, Dual,Boxed"
    controller.paused = False

    ctrl_sleeper_l = create_autospec(SleepIQSleeper)
    ctrl_sleeper_l.side = Side.LEFT
    ctrl_sleeper_l.name = SLEEPER_L_NAME
    ctrl_sleeper_l.sleeper_id = SLEEPER_L_ID
    ctrl_sleeper_l.in_bed = True
    ctrl_sleeper_l.sleep_number = 40
    ctrl_sleeper_l.pressure = 1000
    ctrl_sleeper_l.sleep_data = SleepData(
        duration=28800,
        sleep_score=85,
        heart_rate=60,
        respiratory_rate=14,
        hrv=68,
    )

    ctrl_sleeper_r = create_autospec(SleepIQSleeper)
    ctrl_sleeper_r.side = Side.RIGHT
    ctrl_sleeper_r.name = SLEEPER_R_NAME
    ctrl_sleeper_r.sleeper_id = SLEEPER_R_ID
    ctrl_sleeper_r.in_bed = False
    ctrl_sleeper_r.sleep_number = 80
    ctrl_sleeper_r.pressure = 1400
    ctrl_sleeper_r.sleep_data = SleepData(
        duration=25200,
        sleep_score=78,
        heart_rate=65,
        respiratory_rate=15,
        hrv=72,
    )

    controller.sleepers = [ctrl_sleeper_l, ctrl_sleeper_r]
    controller.foundation = create_autospec(SleepIQFoundation)
    controller.foundation.lights = []
    controller.foundation.actuators = []
    controller.foundation.presets = []
    controller.foundation.foot_warmers = []
    controller.foundation.core_climates = []
    return controller


async def test_duplicate_beds_filtered(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_asyncsleepiq: MagicMock,
) -> None:
    """Test that duplicate bed objects sharing sleeper IDs are filtered."""
    mock_asyncsleepiq.beds["ctrl_001"] = _make_controller()

    entry = await setup_platform(hass, "sensor")
    assert entry.state is ConfigEntryState.LOADED

    sleeper_l_entities = [
        e
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if SLEEPER_L_ID in e.unique_id
    ]
    sleeper_r_entities = [
        e
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if SLEEPER_R_ID in e.unique_id
    ]

    assert len(sleeper_l_entities) > 0
    assert len(sleeper_r_entities) > 0

    bed_ids = list(mock_asyncsleepiq.beds)
    assert "ctrl_001" not in bed_ids
    assert BED_ID in bed_ids


async def test_duplicate_beds_controller_first(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_asyncsleepiq: MagicMock,
) -> None:
    """Test that the real bed survives even when the controller appears first."""
    real_bed = mock_asyncsleepiq.beds.pop(BED_ID)
    mock_asyncsleepiq.beds["ctrl_001"] = _make_controller()
    mock_asyncsleepiq.beds[BED_ID] = real_bed

    entry = await setup_platform(hass, "sensor")
    assert entry.state is ConfigEntryState.LOADED

    bed_ids = list(mock_asyncsleepiq.beds)
    assert BED_ID in bed_ids
    assert "ctrl_001" not in bed_ids


async def test_duplicate_beds_none_sleeper_ids_not_filtered(
    hass: HomeAssistant,
    mock_asyncsleepiq: MagicMock,
) -> None:
    """Test that beds with None sleeper IDs are not falsely treated as duplicates."""
    ghost_bed = create_autospec(SleepIQBed)
    ghost_bed.name = "Guest Bed"
    ghost_bed.id = "ghost_001"
    ghost_bed.mac_addr = "AA:BB:CC:DD:EE:02"
    ghost_bed.model = "Guest"
    ghost_bed.paused = False

    ghost_sleeper = create_autospec(SleepIQSleeper)
    ghost_sleeper.side = Side.LEFT
    ghost_sleeper.name = "Guest"
    ghost_sleeper.sleeper_id = None
    ghost_sleeper.in_bed = False
    ghost_sleeper.sleep_number = 50
    ghost_sleeper.pressure = 1200
    ghost_sleeper.sleep_data = SleepData(
        duration=0, sleep_score=0, heart_rate=0, respiratory_rate=0, hrv=0
    )

    ghost_bed.sleepers = [ghost_sleeper]
    ghost_bed.foundation = create_autospec(SleepIQFoundation)
    ghost_bed.foundation.lights = []
    ghost_bed.foundation.actuators = []
    ghost_bed.foundation.presets = []
    ghost_bed.foundation.foot_warmers = []
    ghost_bed.foundation.core_climates = []

    mock_asyncsleepiq.beds["ghost_001"] = ghost_bed

    entry = await setup_platform(hass, "sensor")
    assert entry.state is ConfigEntryState.LOADED
    assert "ghost_001" in mock_asyncsleepiq.beds
