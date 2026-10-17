"""Tests for the Nobø Ecohub select platform."""

from unittest.mock import MagicMock

from pynobo import PynoboError, nobo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nobo_hub.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import entity_unique_ids, fire_hub_update
from .conftest import SERIAL

from tests.common import MockConfigEntry, snapshot_platform

GLOBAL_ENTITY = "select.my_eco_hub_global_override"
PROFILE_ENTITY = "select.living_room_living_room_week_profile"


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
    ("entity_id", "option", "mock_attr", "expected_key"),
    [
        (
            GLOBAL_ENTITY,
            "eco",
            "async_create_override",
            "set_global_override_failed",
        ),
        (
            PROFILE_ENTITY,
            "Default",
            "async_update_zone",
            "set_week_profile_failed",
        ),
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
    expected_key: str,
) -> None:
    """Library errors during selection are raised as HomeAssistantError."""
    getattr(mock_nobo_hub, mock_attr).side_effect = PynoboError("boom")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == expected_key


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


@pytest.mark.usefixtures("init_integration")
async def test_zone_removed_removes_week_profile_entity(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Removing a zone via the Nobø app must not crash and removes the entity."""
    mock_nobo_hub.zones.pop("1")
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(PROFILE_ENTITY) is None


@pytest.mark.usefixtures("init_integration")
async def test_readded_zone_reappears_profile_selector(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A zone removed and re-added under the same id (the hub reuses ids) restores its selector."""
    entry_id = mock_config_entry.entry_id
    zone = {
        "zone_id": "2",
        "name": "Bedroom",
        "week_profile_id": "0",
        "temp_comfort_c": "22",
        "temp_eco_c": "18",
    }

    mock_nobo_hub.zones["2"] = zone
    await fire_hub_update(hass, mock_nobo_hub)
    assert f"{SERIAL}:2:profile" in entity_unique_ids(entity_registry, entry_id)

    del mock_nobo_hub.zones["2"]
    await fire_hub_update(hass, mock_nobo_hub)
    assert f"{SERIAL}:2:profile" not in entity_unique_ids(entity_registry, entry_id)

    mock_nobo_hub.zones["2"] = zone
    await fire_hub_update(hass, mock_nobo_hub)
    assert f"{SERIAL}:2:profile" in entity_unique_ids(entity_registry, entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_new_zone_adds_profile_selector(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A zone added on the hub at runtime creates a week-profile selector."""
    entry_id = mock_config_entry.entry_id
    assert f"{SERIAL}:2:profile" not in entity_unique_ids(entity_registry, entry_id)

    mock_nobo_hub.zones["2"] = {
        "zone_id": "2",
        "name": "Bedroom",
        "week_profile_id": "0",
        "temp_comfort_c": "22",
        "temp_eco_c": "18",
    }
    await fire_hub_update(hass, mock_nobo_hub)

    assert f"{SERIAL}:2:profile" in entity_unique_ids(entity_registry, entry_id)
