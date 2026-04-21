"""Tests for the Nobø Ecohub select platform."""

from unittest.mock import MagicMock

from pynobo import nobo
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

GLOBAL_ENTITY = "select.my_eco_hub_global_override"
PROFILE_ENTITY = "select.living_room_week_profile"


@pytest.mark.usefixtures("integration_setup")
async def test_global_override_options(hass: HomeAssistant) -> None:
    """Global override exposes the four override modes."""
    state = hass.states.get(GLOBAL_ENTITY)
    assert state is not None
    assert set(state.attributes["options"]) == {"none", "away", "comfort", "eco"}


async def test_global_override_select_away(
    hass: HomeAssistant,
    integration_setup: tuple[MockConfigEntry, MagicMock],
) -> None:
    """Selecting 'away' on the global override applies the away override."""
    _, hub = integration_setup
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: GLOBAL_ENTITY, ATTR_OPTION: "away"},
        blocking=True,
    )
    hub.async_create_override.assert_called_once_with(
        nobo.API.OVERRIDE_MODE_AWAY,
        nobo.API.OVERRIDE_TYPE_CONSTANT,
        nobo.API.OVERRIDE_TARGET_GLOBAL,
    )


@pytest.mark.usefixtures("integration_setup")
async def test_week_profile_options(hass: HomeAssistant) -> None:
    """Week profile options reflect the hub's week profiles."""
    state = hass.states.get(PROFILE_ENTITY)
    assert state is not None
    assert state.attributes["options"] == ["Default"]
    assert state.state == "Default"


async def test_week_profile_select(
    hass: HomeAssistant,
    integration_setup: tuple[MockConfigEntry, MagicMock],
) -> None:
    """Selecting a week profile updates the zone."""
    _, hub = integration_setup
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: PROFILE_ENTITY, ATTR_OPTION: "Default"},
        blocking=True,
    )
    hub.async_update_zone.assert_called_once_with("1", week_profile_id="0")


@pytest.mark.parametrize(
    ("entity_id", "option", "mock_attr"),
    [
        (GLOBAL_ENTITY, "eco", "async_create_override"),
        (PROFILE_ENTITY, "Default", "async_update_zone"),
    ],
    ids=["global_override", "week_profile"],
)
async def test_select_option_wraps_library_error(
    hass: HomeAssistant,
    integration_setup: tuple[MockConfigEntry, MagicMock],
    entity_id: str,
    option: str,
    mock_attr: str,
) -> None:
    """Library errors during selection are raised as HomeAssistantError."""
    _, hub = integration_setup
    getattr(hub, mock_attr).side_effect = OSError("boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
            blocking=True,
        )


async def test_global_override_push_update(
    hass: HomeAssistant,
    integration_setup: tuple[MockConfigEntry, MagicMock],
) -> None:
    """Pushed hub updates refresh the global override state."""
    _, hub = integration_setup
    assert hass.states.get(GLOBAL_ENTITY).state == "none"

    hub.overrides = {
        "988": {
            "mode": nobo.API.OVERRIDE_MODE_COMFORT,
            "target_type": nobo.API.OVERRIDE_TARGET_GLOBAL,
            "target_id": "-1",
        },
    }
    for call in hub.register_callback.call_args_list:
        call.args[0](hub)
    await hass.async_block_till_done()
    assert hass.states.get(GLOBAL_ENTITY).state == "comfort"


async def test_week_profile_push_update(
    hass: HomeAssistant,
    integration_setup: tuple[MockConfigEntry, MagicMock],
) -> None:
    """Pushed hub updates refresh the week profile state."""
    _, hub = integration_setup
    assert hass.states.get(PROFILE_ENTITY).state == "Default"

    hub.week_profiles = {
        "0": {"week_profile_id": "0", "name": "Default", "profile": "00000"},
        "1": {"week_profile_id": "1", "name": "Weekend", "profile": "00001"},
    }
    hub.zones["1"]["week_profile_id"] = "1"
    for call in hub.register_callback.call_args_list:
        call.args[0](hub)
    await hass.async_block_till_done()
    assert hass.states.get(PROFILE_ENTITY).state == "Weekend"
