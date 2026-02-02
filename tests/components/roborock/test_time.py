"""Test Roborock Time platform."""

from datetime import time

import pytest
import roborock
from roborock.data import DnDTimer

from homeassistant.components.time import SERVICE_SET_VALUE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import FakeDevice

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.TIME]


@pytest.mark.parametrize(
    ("entity_id", "start_state", "expected_args", "end_state"),
    [
        (
            "time.roborock_s7_maxv_do_not_disturb_begin",
            "22:00:00",
            DnDTimer(start_hour=1, start_minute=1, end_hour=7, end_minute=0, enabled=1),
            "01:01:00",
        ),
        (
            "time.roborock_s7_maxv_do_not_disturb_end",
            "07:00:00",
            DnDTimer(
                start_hour=22, start_minute=0, end_hour=1, end_minute=1, enabled=1
            ),
            "01:01:00",
        ),
    ],
)
async def test_update_success(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    entity_id: str,
    start_state: str,
    end_state: str,
    expected_args: DnDTimer,
) -> None:
    """Test turning switch entities on and off."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == start_state

    await hass.services.async_call(
        "time",
        SERVICE_SET_VALUE,
        service_data={"time": time(hour=1, minute=1)},
        blocking=True,
        target={"entity_id": entity_id},
    )

    assert fake_vacuum.v1_properties.dnd.set_dnd_timer.call_count == 1
    # Since we update the begin or end time separately: Verify that the args are built properly
    # by reading the existing value and only updating the relevant fields.
    assert fake_vacuum.v1_properties.dnd.set_dnd_timer.call_args == ((expected_args,),)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == end_state


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("time.roborock_s7_maxv_do_not_disturb_begin"),
    ],
)
async def test_update_failure(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
    fake_vacuum: FakeDevice,
) -> None:
    """Test turning switch entities on and off."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    fake_vacuum.v1_properties.dnd.set_dnd_timer.side_effect = (
        roborock.exceptions.RoborockTimeout
    )
    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "time",
            SERVICE_SET_VALUE,
            service_data={"time": time(hour=1, minute=1)},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert fake_vacuum.v1_properties.dnd.set_dnd_timer.call_count == 1
