"""Number tests for the SABnzbd component."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysabnzbd import SabnzbdApiException
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@patch("homeassistant.components.sabnzbd.PLATFORMS", [Platform.NUMBER])
async def test_number_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test number setup."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("number", "input_number", "called_function", "expected_state"),
    [
        ("speedlimit", 50.0, "set_speed_limit", 50),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_number_set(
    hass: HomeAssistant,
    sabnzbd: AsyncMock,
    number: str,
    input_number: float,
    called_function: str,
    expected_state: str,
) -> None:
    """Test the sabnzbd number set."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_VALUE: input_number,
            ATTR_ENTITY_ID: f"number.sabnzbd_{number}",
        },
        blocking=True,
    )

    function = getattr(sabnzbd, called_function)
    function.assert_called_with(int(input_number))


@pytest.mark.parametrize(
    ("number", "input_number", "called_function"),
    [("speedlimit", 55.0, "set_speed_limit")],
)
@pytest.mark.usefixtures("setup_integration")
async def test_number_exception(
    hass: HomeAssistant,
    sabnzbd: AsyncMock,
    number: str,
    input_number: float,
    called_function: str,
) -> None:
    """Test the number entity handles errors."""
    function = getattr(sabnzbd, called_function)
    function.side_effect = SabnzbdApiException("Boom")

    with pytest.raises(
        HomeAssistantError,
        match="Unable to send command to SABnzbd due to a connection error, try again later",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_VALUE: input_number,
                ATTR_ENTITY_ID: f"number.sabnzbd_{number}",
            },
            blocking=True,
        )

    function.assert_called_once()


@pytest.mark.parametrize(
    ("number", "initial_state"),
    [("speedlimit", "85")],
)
@pytest.mark.usefixtures("setup_integration")
async def test_number_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    sabnzbd: AsyncMock,
    number: str,
    initial_state: str,
) -> None:
    """Test the number is unavailable when coordinator can't update data."""
    state = hass.states.get(f"number.sabnzbd_{number}")
    assert state
    assert state.state == initial_state

    sabnzbd.refresh_data.side_effect = Exception("Boom")
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"number.sabnzbd_{number}")
    assert state
    assert state.state == STATE_UNAVAILABLE
