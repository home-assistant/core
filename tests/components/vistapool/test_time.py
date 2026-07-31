"""Tests for the Vistapool time platform."""

from collections.abc import Generator
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
    ],
)
async def test_time_native_value_unknown_when_unparsable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    raw_value: Any,
) -> None:
    """Test a non-numeric or missing raw value yields an unknown state."""
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
    ("entity_id", "expected_path"),
    [
        pytest.param(
            "time.my_pool_filtration_interval_1_start",
            "filtration.interval1.from",
            id="interval_1_start",
        ),
        pytest.param(
            "time.my_pool_filtration_interval_2_end",
            "filtration.interval2.to",
            id="interval_2_end",
        ),
    ],
)
async def test_time_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
    entity_id: str,
    expected_path: str,
) -> None:
    """Test set_value encodes the time as seconds since midnight at the right path."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: "12:30:00"},
        blocking=True,
    )

    # 12:30 -> 12 * 3600 + 30 * 60 = 45000 seconds.
    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", expected_path, 45000
    )
    assert hass.states.get(entity_id).state == "12:30:00"


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
