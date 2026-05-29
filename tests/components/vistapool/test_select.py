"""Tests for the Vistapool select platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from aioaquarite import AquariteError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def _only_select_platform() -> Generator[None]:
    """Restrict integration setup to the select platform for these tests."""
    with patch("homeassistant.components.vistapool.PLATFORMS", [Platform.SELECT]):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test select entities for the default fixture."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("raw_value", "expected_option"),
    [
        pytest.param(0, "manual", id="index_0"),
        pytest.param(2, "heat", id="index_2"),
        pytest.param(4, "intel", id="index_4"),
        pytest.param("3", "smart", id="string_index"),
    ],
)
async def test_select_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    raw_value: int | str,
    expected_option: str,
) -> None:
    """Test current_option maps the API integer (or stringified int) onto the option name."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"mode": raw_value},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("select.my_pool_pump_mode").state == expected_option


@pytest.mark.parametrize(
    "raw_value",
    [
        pytest.param(None, id="missing"),
        pytest.param("garbage", id="non_numeric"),
        pytest.param(99, id="out_of_range"),
    ],
)
async def test_select_current_option_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    raw_value: Any,
) -> None:
    """Test current_option reports unknown for missing / unparseable / out-of-range raw values."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"mode": raw_value},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("select.my_pool_pump_mode").state == "unknown"


@pytest.mark.parametrize(
    ("entity_id", "option", "expected_path", "expected_index"),
    [
        pytest.param(
            "select.my_pool_pump_mode",
            "heat",
            "filtration.mode",
            2,
            id="pump_mode_heat",
        ),
        pytest.param(
            "select.my_pool_pump_speed",
            "medium",
            "filtration.manVel",
            1,
            id="pump_speed_medium",
        ),
        pytest.param(
            "select.my_pool_filtration_timer_speed_2",
            "high",
            "filtration.timerVel2",
            2,
            id="timer_2_high",
        ),
    ],
)
async def test_select_option_writes_index(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
    entity_id: str,
    option: str,
    expected_path: str,
    expected_index: int,
) -> None:
    """Test select_option writes the option's index to the right API path."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", expected_path, expected_index
    )


async def test_select_option_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test select_option re-raises as HomeAssistantError when the library fails."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_vistapool_client.set_value.side_effect = AquariteError("boom")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.my_pool_pump_mode", ATTR_OPTION: "heat"},
            blocking=True,
        )
