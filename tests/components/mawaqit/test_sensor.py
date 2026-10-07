"""Tests for the MAWAQIT sensors."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from mawaqit import MawaqitError
from mawaqit.types import PrayerTimes
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# Times of the fixture, in Paris (UTC+2): Thursday 9 April 2026 has Fajr at 05:35,
# Dhuhr at 13:57, Asr at 17:35 and Isha at 22:03. Friday 10 April has Fajr at 05:33
# and Jumua at 13:50 and 14:30.


@pytest.mark.freeze_time("2026-04-09 10:00:00+00:00")
@pytest.mark.usefixtures("mock_mawaqit_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all the sensors."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("update", "missing", "present"),
    [
        pytest.param(
            {"iqama_enabled": False},
            ["sensor.fajr_iqama", "sensor.isha_iqama"],
            ["sensor.jumua_prayer"],
            id="no_iqama",
        ),
        pytest.param(
            {"jumua_2": None},
            ["sensor.second_jumua_prayer", "sensor.third_jumua_prayer"],
            ["sensor.jumua_prayer", "sensor.fajr_iqama"],
            id="one_jumua",
        ),
        pytest.param(
            {"jumua": None, "jumua_2": None},
            ["sensor.jumua_prayer", "sensor.second_jumua_prayer"],
            ["sensor.dhuhr_prayer"],
            id="no_jumua",
        ),
    ],
)
@pytest.mark.freeze_time("2026-04-09 10:00:00+00:00")
async def test_optional_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mawaqit_client: MagicMock,
    prayer_times: PrayerTimes,
    update: dict[str, Any],
    missing: list[str],
    present: list[str],
) -> None:
    """Test the iqama and Jumua sensors are only created when the mosque has them."""
    mock_mawaqit_client.mosques.prayer_times.return_value = prayer_times.model_copy(
        update=update
    )
    await setup_integration(hass, mock_config_entry)

    for entity_id in missing:
        assert hass.states.get(entity_id) is None
    for entity_id in present:
        assert hass.states.get(entity_id) is not None


@pytest.mark.freeze_time("2026-04-09 10:00:00+00:00")
async def test_jumua_as_dhuhr(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mawaqit_client: MagicMock,
    prayer_times: PrayerTimes,
) -> None:
    """Test Jumua is at the time of Dhuhr when the mosque says so."""
    mock_mawaqit_client.mosques.prayer_times.return_value = prayer_times.model_copy(
        update={"jumua": None, "jumua_2": None, "jumua_as_duhr": True}
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.jumua_prayer").state == "2026-04-10T11:57:00+00:00"


@pytest.mark.freeze_time("2026-04-09 21:00:00+00:00")
@pytest.mark.usefixtures("mock_mawaqit_client")
async def test_day_changes_halfway_through_the_night(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the prayers of the next day are shown halfway between Isha and Fajr."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.fajr_prayer").state == "2026-04-09T03:35:00+00:00"
    assert hass.states.get("sensor.jumua_prayer").state == "2026-04-10T11:50:00+00:00"

    # Halfway between 22:03 and 05:33 is 01:48.
    freezer.move_to("2026-04-09 23:47:59+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.fajr_prayer").state == "2026-04-09T03:35:00+00:00"

    freezer.move_to("2026-04-09 23:48:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.fajr_prayer").state == "2026-04-10T03:33:00+00:00"
    assert hass.states.get("sensor.jumua_prayer").state == "2026-04-10T11:50:00+00:00"


@pytest.mark.parametrize(
    ("now", "name", "time"),
    [
        pytest.param(
            "2026-04-09 10:00:00+00:00",
            "dhuhr",
            "2026-04-09T11:57:00+00:00",
            id="thursday",
        ),
        pytest.param(
            "2026-04-10 10:00:00+00:00",
            "jumua",
            "2026-04-10T11:50:00+00:00",
            id="friday",
        ),
        pytest.param(
            "2026-04-09 21:00:00+00:00",
            "fajr",
            "2026-04-10T03:33:00+00:00",
            id="after_isha",
        ),
    ],
)
@pytest.mark.usefixtures("mock_mawaqit_client")
async def test_next_prayer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    now: str,
    name: str,
    time: str,
) -> None:
    """Test the next prayer."""
    freezer.move_to(now)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.next_salat").state == name
    assert hass.states.get("sensor.next_salat_time").state == time


@pytest.mark.freeze_time("2026-04-09 10:00:00+00:00")
@pytest.mark.usefixtures("mock_mawaqit_client")
async def test_next_prayer_changes_when_it_starts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the next prayer moves on when its time comes."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.next_salat").state == "dhuhr"

    freezer.move_to("2026-04-09 11:57:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.next_salat").state == "asr"
    assert (
        hass.states.get("sensor.next_salat_time").state == "2026-04-09T15:35:00+00:00"
    )


@pytest.mark.freeze_time("2026-04-09 10:00:00+00:00")
async def test_no_times_in_the_calendar(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mawaqit_client: MagicMock,
    prayer_times: PrayerTimes,
) -> None:
    """Test the sensors are unknown when the calendar has no times for now."""
    mock_mawaqit_client.mosques.prayer_times.return_value = prayer_times.model_copy(
        update={"calendar": []}
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.fajr_prayer").state == STATE_UNKNOWN
    assert hass.states.get("sensor.next_salat").state == STATE_UNKNOWN


@pytest.mark.freeze_time("2026-04-09 10:00:00+00:00")
async def test_unavailable_when_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mawaqit_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors are unavailable when the prayer times cannot be fetched."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.fajr_prayer").state != STATE_UNAVAILABLE

    mock_mawaqit_client.mosques.prayer_times.side_effect = MawaqitError
    freezer.tick(timedelta(hours=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.fajr_prayer").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.next_salat").state == STATE_UNAVAILABLE
