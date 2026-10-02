"""Tests for the Vistapool time platform."""

from collections.abc import Generator
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

from aioaquarite import AquariteError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def _only_time_platform() -> Generator[None]:
    """Restrict integration setup to the time platform for these tests."""
    with patch("homeassistant.components.vistapool.PLATFORMS", [Platform.TIME]):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test time entities for the default fixture."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_time_decodes_seconds_since_midnight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test the stored seconds-since-midnight are decoded to a time."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fixture stores interval1 from=28800 (08:00) and to=36000 (10:00).
    assert hass.states.get("time.my_pool_filtration_interval_1_start").state == (
        "08:00:00"
    )
    assert hass.states.get("time.my_pool_filtration_interval_1_end").state == "10:00:00"


@pytest.mark.parametrize(
    "raw_value",
    [
        pytest.param("garbage", id="non_numeric"),
        pytest.param(None, id="missing"),
        pytest.param(86400, id="out_of_range_high"),
        pytest.param(-60, id="negative"),
    ],
)
async def test_time_native_value_unknown_when_unparsable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    raw_value: Any,
) -> None:
    """Test an unparsable or out-of-range raw value yields an unknown state."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"interval1": {"from": raw_value}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("time.my_pool_filtration_interval_1_start").state == "unknown"
    )


@pytest.mark.parametrize(
    ("entity_id", "time_value", "expected_path", "expected_seconds"),
    [
        pytest.param(
            "time.my_pool_filtration_interval_1_start",
            "12:30:00",
            "filtration.interval1.from",
            45000,
            id="interval_1_start",
        ),
        pytest.param(
            "time.my_pool_filtration_interval_2_end",
            "12:30:00",
            "filtration.interval2.to",
            45000,
            id="interval_2_end",
        ),
        pytest.param(
            "time.my_pool_filtration_interval_3_start",
            "07:05:09",
            "filtration.interval3.from",
            25509,
            id="interval_3_start_with_seconds",
        ),
    ],
)
async def test_time_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
    entity_id: str,
    time_value: str,
    expected_path: str,
    expected_seconds: int,
) -> None:
    """Test set_value encodes the time as seconds since midnight at the right path."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: time_value},
        blocking=True,
    )

    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", expected_path, expected_seconds
    )
    assert hass.states.get(entity_id).state == time_value


async def test_time_set_value_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test set_value re-raises as HomeAssistantError when the library fails."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_vistapool_client.set_value.side_effect = AquariteError("boom")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "time.my_pool_filtration_interval_1_start",
                ATTR_TIME: "12:30:00",
            },
            blocking=True,
        )
    assert excinfo.value.translation_key == "set_failed"


_LIGHT_SCHEDULE_DATA = {
    "main": {"version": 1},
    "light": {"mode": 1, "status": 0, "from": 79200, "to": 3600},
}


async def test_light_schedule_times_not_created_without_scheduling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test controllers without light scheduling do not get the light times."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("time.my_pool_light_schedule_start") is None
    assert hass.states.get("time.my_pool_light_schedule_end") is None


async def test_light_schedule_times_decode_seconds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the light schedule bounds decode from seconds since midnight."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LIGHT_SCHEDULE_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # 79200 is 22:00, 3600 is 01:00 the next morning.
    assert hass.states.get("time.my_pool_light_schedule_start").state == "22:00:00"
    assert hass.states.get("time.my_pool_light_schedule_end").state == "01:00:00"


async def test_light_schedule_time_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test setting a light schedule bound writes seconds since midnight."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LIGHT_SCHEDULE_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "time.my_pool_light_schedule_start", ATTR_TIME: "21:30:00"},
        blocking=True,
    )

    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", "light.from", 77400
    )


async def test_light_schedule_time_created_for_midnight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a schedule bound of zero seconds still creates the entity.

    Zero is midnight, a legitimate schedule bound, not a missing field.
    """
    data = deepcopy(_LIGHT_SCHEDULE_DATA)
    data["light"]["from"] = 0
    mock_vistapool_client.fetch_pool_data.return_value = data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("time.my_pool_light_schedule_start").state == "00:00:00"
