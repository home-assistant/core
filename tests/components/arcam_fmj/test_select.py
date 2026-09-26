"""Tests for Arcam FMJ select entities."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from arcam.fmj.codecs import RoomEqMode
from arcam.fmj.state import State
import pytest

from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

ROOM_EQ_ENTITY_ID = "select.arcam_fmj_127_0_0_1_room_equalization"


@pytest.fixture(autouse=True)
def select_only() -> Generator[None]:
    """Limit platform setup to select only."""
    with patch("homeassistant.components.arcam_fmj.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.usefixtures("player_setup")
async def test_room_eq_options(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test named Room EQ profiles and per-slot fallbacks."""
    state_1.get_room_eq_names.return_value = ["Front Row", "Front Row", "Off"]
    state_1.get_room_equalization.return_value = RoomEqMode.EQ2

    client.notify_data_updated()
    await hass.async_block_till_done()

    state = hass.states.get(ROOM_EQ_ENTITY_ID)
    assert state is not None
    assert state.state == "EQ2: Front Row"
    assert state.attributes["options"] == [
        "Off",
        "EQ1: Front Row",
        "EQ2: Front Row",
        "EQ3: Off",
    ]


@pytest.mark.usefixtures("player_setup")
async def test_room_eq_not_calculated(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test an uncalculated Room EQ profile is represented as an option."""
    state_1.get_room_equalization.return_value = RoomEqMode.NOT_CALCULATED

    client.notify_data_updated()
    await hass.async_block_till_done()

    state = hass.states.get(ROOM_EQ_ENTITY_ID)
    assert state is not None
    assert state.state == "Not calculated"
    assert "Not calculated" in state.attributes["options"]


@pytest.mark.usefixtures("player_setup")
async def test_select_room_eq_profile(
    hass: HomeAssistant,
    state_1: State,
) -> None:
    """Test selecting a named Room EQ profile."""
    state_1.get_room_eq_names.return_value = ["Front Row", "Back Row"]

    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        service_data={
            ATTR_ENTITY_ID: ROOM_EQ_ENTITY_ID,
            ATTR_OPTION: "EQ2: Back Row",
        },
        blocking=True,
    )

    state_1.set_room_equalization.assert_awaited_once_with(RoomEqMode.EQ2)


@pytest.mark.usefixtures("player_setup")
async def test_select_not_calculated(
    hass: HomeAssistant,
    state_1: State,
) -> None:
    """Test that the non-actionable Not calculated state cannot be selected."""
    state_1.get_room_equalization.return_value = RoomEqMode.NOT_CALCULATED

    with pytest.raises(
        ServiceValidationError,
        check=lambda exception: (
            exception.translation_domain == "arcam_fmj"
            and exception.translation_key == "unsupported_room_equalization"
        ),
    ):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={
                ATTR_ENTITY_ID: ROOM_EQ_ENTITY_ID,
                ATTR_OPTION: "Not calculated",
            },
            blocking=True,
        )

    state_1.set_room_equalization.assert_not_awaited()
