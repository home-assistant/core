"""Tests for the Qube Heat Pump select platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "select.qube_heat_pump"


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all select entities via snapshot."""
    with patch(
        "homeassistant.components.hr_energy_qube.PLATFORMS",
        [Platform.SELECT],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("option", ["block", "plus", "max"])
async def test_select_option(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    option: str,
) -> None:
    """Test selecting an SG Ready mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )

    mock_qube_client.set_sg_ready_mode.assert_awaited_once_with(option)


async def test_select_option_connection_error(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test select raises HomeAssistantError on connection error."""
    await setup_integration(hass, mock_config_entry)

    mock_qube_client.set_sg_ready_mode = AsyncMock(side_effect=ConnectionError)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "plus"},
            blocking=True,
        )


async def test_select_option_write_failure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test select raises HomeAssistantError when write fails."""
    await setup_integration(hass, mock_config_entry)

    mock_qube_client.set_sg_ready_mode = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "plus"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (ConnectionError("Connection lost"), None),
        (None, None),
    ],
)
async def test_select_unavailable_on_coordinator_error(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception | None,
    return_value: None,
) -> None:
    """Test select becomes unavailable when coordinator fails."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_qube_client.get_all_data = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
