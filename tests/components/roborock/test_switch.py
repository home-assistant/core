"""Test Roborock Switch platform."""

from collections.abc import Callable
from typing import Any

import pytest
import roborock

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import FakeDevice

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SWITCH]


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("switch.roborock_s7_maxv_dock_child_lock"),
        ("switch.roborock_s7_maxv_dock_status_indicator_light"),
        ("switch.roborock_s7_maxv_do_not_disturb"),
    ],
)
async def test_update_success(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test turning switch entities on and off."""
    # The entity fixture in conftest.py starts with the switch on and will
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Turn off the switch and verify the entity state is updated properly with
    # the latest information from the trait.
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Turn back on and verify the entity state is updated properly with the
    # latest information from the trait
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    ("entity_id", "service", "expected_call_fn"),
    [
        (
            "switch.roborock_s7_maxv_dock_status_indicator_light",
            SERVICE_TURN_ON,
            lambda trait: trait.flow_led_status.enable,
        ),
        (
            "switch.roborock_s7_maxv_dock_status_indicator_light",
            SERVICE_TURN_OFF,
            lambda trait: trait.flow_led_status.disable,
        ),
    ],
)
@pytest.mark.parametrize(
    "send_message_exception", [roborock.exceptions.RoborockTimeout]
)
async def test_update_failed(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
    service: str,
    fake_vacuum: FakeDevice,
    expected_call_fn: Callable[[Any], Any],
) -> None:
    """Test a failure while updating a switch."""

    expected_call = expected_call_fn(fake_vacuum.v1_properties)
    expected_call.side_effect = roborock.exceptions.RoborockTimeout

    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    with (
        pytest.raises(HomeAssistantError, match="Failed to update Roborock options"),
    ):
        await hass.services.async_call(
            "switch",
            service,
            service_data=None,
            blocking=True,
            target={"entity_id": entity_id},
        )

    assert len(expected_call.mock_calls) == 1
