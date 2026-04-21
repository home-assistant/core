"""Tests for the Nobø Ecohub select platform."""

from unittest.mock import MagicMock

from pynobo import nobo
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

from . import fire_hub_update

from tests.common import MockConfigEntry, snapshot_platform

GLOBAL_ENTITY = "select.my_eco_hub_global_override"
PROFILE_ENTITY = "select.living_room_week_profile"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the select platform for these tests."""
    return [Platform.SELECT]


@pytest.mark.usefixtures("init_integration")
async def test_select_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """All select entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_global_override_select_away(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Selecting 'away' on the global override applies the away override."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: GLOBAL_ENTITY, ATTR_OPTION: "away"},
        blocking=True,
    )
    mock_nobo_hub.async_create_override.assert_called_once_with(
        nobo.API.OVERRIDE_MODE_AWAY,
        nobo.API.OVERRIDE_TYPE_CONSTANT,
        nobo.API.OVERRIDE_TARGET_GLOBAL,
    )


@pytest.mark.usefixtures("init_integration")
async def test_week_profile_select(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Selecting a week profile updates the zone."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: PROFILE_ENTITY, ATTR_OPTION: "Default"},
        blocking=True,
    )
    mock_nobo_hub.async_update_zone.assert_called_once_with("1", week_profile_id="0")


@pytest.mark.parametrize(
    ("entity_id", "option", "mock_attr"),
    [
        (GLOBAL_ENTITY, "eco", "async_create_override"),
        (PROFILE_ENTITY, "Default", "async_update_zone"),
    ],
    ids=["global_override", "week_profile"],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_option_wraps_library_error(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    entity_id: str,
    option: str,
    mock_attr: str,
) -> None:
    """Library errors during selection are raised as HomeAssistantError."""
    getattr(mock_nobo_hub, mock_attr).side_effect = OSError("boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_global_override_push_update(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Pushed hub updates refresh the global override state."""
    assert hass.states.get(GLOBAL_ENTITY).state == "none"

    mock_nobo_hub.overrides = {
        "988": {
            "mode": nobo.API.OVERRIDE_MODE_COMFORT,
            "target_type": nobo.API.OVERRIDE_TARGET_GLOBAL,
            "target_id": "-1",
        },
    }
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(GLOBAL_ENTITY).state == "comfort"


@pytest.mark.usefixtures("init_integration")
async def test_week_profile_push_update(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Pushed hub updates refresh the week profile state."""
    assert hass.states.get(PROFILE_ENTITY).state == "Default"

    mock_nobo_hub.week_profiles = {
        "0": {"week_profile_id": "0", "name": "Default", "profile": "00000"},
        "1": {"week_profile_id": "1", "name": "Weekend", "profile": "00001"},
    }
    mock_nobo_hub.zones["1"]["week_profile_id"] = "1"
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(PROFILE_ENTITY).state == "Weekend"
