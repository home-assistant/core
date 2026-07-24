"""Tests for the Panasonic Window A/C Quiet/Powerful button platform."""

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.panasonic_window_ac_hk.command import (
    PanasonicWindowAcHKCommand,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.parametrize(
    ("entity_id", "expected_kind"),
    [
        ("button.panasonic_window_ac_hong_kong_quiet", "quiet"),
        ("button.panasonic_window_ac_hong_kong_powerful", "powerful"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_press_sends_short_frame(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_kind: str,
) -> None:
    """Test pressing a button sends the matching short toggle frame."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings() == (
        PanasonicWindowAcHKCommand.short(expected_kind).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(hass: HomeAssistant) -> None:
    """Test a button follows the infrared emitter availability."""
    await assert_availability_follows_source_entity(
        hass, "button.panasonic_window_ac_hong_kong_quiet", EMITTER_ENTITY_ID
    )
