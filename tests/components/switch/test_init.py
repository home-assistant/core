"""The tests for the Switch component."""

import pytest

from homeassistant import core
from homeassistant.components import switch
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import common
from .common import MockSwitch

from tests.common import (
    MockUser,
    help_test_all,
    import_and_test_deprecated_constant_enum,
    setup_test_component_platform,
)


@pytest.fixture(autouse=True)
def entities(hass: HomeAssistant, mock_switch_entities: list[MockSwitch]):
    """Initialize the test switch."""
    setup_test_component_platform(hass, switch.DOMAIN, mock_switch_entities)
    return mock_switch_entities


async def test_methods(
    hass: HomeAssistant, entities, enable_custom_integrations: None
) -> None:
    """Test is_on, turn_on, turn_off methods."""
    switch_1, switch_2, switch_3 = entities
    assert await async_setup_component(
        hass, switch.DOMAIN, {switch.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()
    assert switch.is_on(hass, switch_1.entity_id)
    assert not switch.is_on(hass, switch_2.entity_id)
    assert not switch.is_on(hass, switch_3.entity_id)

    await common.async_turn_off(hass, switch_1.entity_id)
    await common.async_turn_on(hass, switch_2.entity_id)

    assert not switch.is_on(hass, switch_1.entity_id)
    assert switch.is_on(hass, switch_2.entity_id)

    # Turn all off
    await common.async_turn_off(hass)

    assert not switch.is_on(hass, switch_1.entity_id)
    assert not switch.is_on(hass, switch_2.entity_id)
    assert not switch.is_on(hass, switch_3.entity_id)

    # Turn all on
    await common.async_turn_on(hass)

    assert switch.is_on(hass, switch_1.entity_id)
    assert switch.is_on(hass, switch_2.entity_id)
    assert switch.is_on(hass, switch_3.entity_id)


async def test_switch_context(
    hass: HomeAssistant,
    entities,
    hass_admin_user: MockUser,
    enable_custom_integrations: None,
) -> None:
    """Test that switch context works."""
    assert await async_setup_component(hass, "switch", {"switch": {"platform": "test"}})

    await hass.async_block_till_done()

    state = hass.states.get("switch.ac")
    assert state is not None

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": state.entity_id},
        True,
        core.Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get("switch.ac")
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(switch)


@pytest.mark.parametrize(("enum"), list(switch.SwitchDeviceClass))
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: switch.SwitchDeviceClass,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, switch, enum, "DEVICE_CLASS_", "2025.1"
    )
