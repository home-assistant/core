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
    ("entity_id", "expected_args"),
    [
        (
            "time.roborock_s7_maxv_do_not_disturb_begin",
            DnDTimer(start_hour=1, start_minute=1, end_hour=7, end_minute=0, enabled=1),
        ),
        (
            "time.roborock_s7_maxv_do_not_disturb_end",
            DnDTimer(
                start_hour=22, start_minute=0, end_hour=1, end_minute=1, enabled=1
            ),
        ),
    ],
)
async def test_update_success(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    entity_id: str,
    expected_args: DnDTimer,
) -> None:
    """Test turning switch entities on and off."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "time",
        SERVICE_SET_VALUE,
        service_data={"time": time(hour=1, minute=1)},
        blocking=True,
        target={"entity_id": entity_id},
    )

    assert fake_vacuum.v1_properties.dnd.set_dnd_timer.call_count == 1
    assert fake_vacuum.v1_properties.dnd.set_dnd_timer.call_args == ((expected_args,),)


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
